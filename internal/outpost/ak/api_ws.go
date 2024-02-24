package ak

import (
	"context"
	"crypto/tls"
	"fmt"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"

	"github.com/gorilla/websocket"
	"github.com/prometheus/client_golang/prometheus"
	"goauthentik.io/internal/config"
	"goauthentik.io/internal/constants"
)

func (ac *APIController) initWS(akURL url.URL, outpostUUID string) error {
	pathTemplate := "%s://%s%sws/outpost/%s/?%s"
	query := akURL.Query()
	query.Set("instance_uuid", ac.instanceUUID.String())
	scheme := strings.ReplaceAll(akURL.Scheme, "http", "ws")

	authHeader := fmt.Sprintf("Bearer %s", ac.token)

	header := http.Header{
		"Authorization": []string{authHeader},
		"User-Agent":    []string{constants.OutpostUserAgent()},
	}

	dialer := websocket.Dialer{
		Proxy:            http.ProxyFromEnvironment,
		HandshakeTimeout: 10 * time.Second,
		TLSClientConfig: &tls.Config{
			InsecureSkipVerify: config.Get().AuthentikInsecure,
		},
	}

	ws, _, err := dialer.Dial(fmt.Sprintf(pathTemplate, scheme, akURL.Host, akURL.Path, outpostUUID, akURL.Query().Encode()), header)
	if err != nil {
		ac.logger.WithError(err).Warning("failed to connect websocket")
		return err
	}

	ac.wsConn = ws
	// Send hello message with our version
	msg := websocketMessage{
		Instruction: WebsocketInstructionHello,
		Args:        ac.getWebsocketPingArgs(),
	}
	err = ws.WriteJSON(msg)
	if err != nil {
		ac.logger.WithField("logger", "authentik.outpost.ak-ws").WithError(err).Warning("Failed to hello to authentik")
		return err
	}
	ac.lastWsReconnect = time.Now()
	ac.logger.WithField("logger", "authentik.outpost.ak-ws").WithField("outpost", outpostUUID).Info("Successfully connected websocket")
	return nil
}

// Shutdown Gracefully stops all workers, disconnects from websocket
func (ac *APIController) Shutdown() {
	// Cleanly close the connection by sending a close message and then
	// waiting (with timeout) for the server to close the connection.
	err := ac.wsConn.WriteMessage(websocket.CloseMessage, websocket.FormatCloseMessage(websocket.CloseNormalClosure, ""))
	if err != nil {
		ac.logger.WithError(err).Warning("failed to write close message")
		return
	}
	err = ac.wsConn.Close()
	if err != nil {
		ac.logger.WithError(err).Warning("failed to close websocket")
	}
	ac.logger.Info("finished shutdown")
}

func (ac *APIController) reconnectWS() {
	if ac.wsIsReconnecting {
		return
	}
	ac.wsIsReconnecting = true
	u := url.URL{
		Host:   ac.Client.GetConfig().Host,
		Scheme: ac.Client.GetConfig().Scheme,
		Path:   strings.ReplaceAll(ac.Client.GetConfig().Servers[0].URL, "api/v3", ""),
	}
	attempt := 1
	for {
		q := u.Query()
		q.Set("attempt", strconv.Itoa(attempt))
		u.RawQuery = q.Encode()
		err := ac.initWS(u, ac.Outpost.Pk)
		attempt += 1
		if err != nil {
			ac.logger.Infof("waiting %d seconds to reconnect", ac.wsBackoffMultiplier)
			time.Sleep(time.Duration(ac.wsBackoffMultiplier) * time.Second)
			ac.wsBackoffMultiplier = ac.wsBackoffMultiplier * 2
			// Limit to 300 seconds (5m)
			if ac.wsBackoffMultiplier >= 300 {
				ac.wsBackoffMultiplier = 300
			}
		} else {
			ac.wsIsReconnecting = false
			ac.wsBackoffMultiplier = 1
			return
		}
	}
}

func (ac *APIController) startWSHandler() {
	logger := ac.logger.WithField("loop", "ws-handler")
	for {
		var wsMsg websocketMessage
		if ac.wsConn == nil {
			go ac.reconnectWS()
			time.Sleep(time.Second * 5)
			continue
		}
		err := ac.wsConn.ReadJSON(&wsMsg)
		if err != nil {
			ConnectionStatus.With(prometheus.Labels{
				"outpost_name": ac.Outpost.Name,
				"outpost_type": ac.Server.Type(),
				"uuid":         ac.instanceUUID.String(),
			}).Set(0)
			logger.WithError(err).Warning("ws read error")
			go ac.reconnectWS()
			time.Sleep(time.Second * 5)
			continue
		}
		ConnectionStatus.With(prometheus.Labels{
			"outpost_name": ac.Outpost.Name,
			"outpost_type": ac.Server.Type(),
			"uuid":         ac.instanceUUID.String(),
		}).Set(1)
		if wsMsg.Instruction == WebsocketInstructionTriggerUpdate {
			time.Sleep(ac.reloadOffset)
			logger.Debug("Got update trigger...")
			err := ac.OnRefresh()
			if err != nil {
				logger.WithError(err).Debug("Failed to update")
			} else {
				LastUpdate.With(prometheus.Labels{
					"outpost_name": ac.Outpost.Name,
					"outpost_type": ac.Server.Type(),
					"uuid":         ac.instanceUUID.String(),
					"version":      constants.VERSION,
					"build":        constants.BUILD("tagged"),
				}).SetToCurrentTime()
			}
		} else if wsMsg.Instruction == WebsocketInstructionProviderSpecific {
			for _, h := range ac.wsHandlers {
				h(context.Background(), wsMsg.Args)
			}
		}
	}
}

func (ac *APIController) startWSHealth() {
	ticker := time.NewTicker(time.Second * 10)
	for ; true; <-ticker.C {
		if ac.wsConn == nil {
			go ac.reconnectWS()
			time.Sleep(time.Second * 5)
			continue
		}
		err := ac.SendWSHello(map[string]interface{}{})
		if err != nil {
			ac.logger.WithField("loop", "ws-health").WithError(err).Warning("ws write error")
			go ac.reconnectWS()
			time.Sleep(time.Second * 5)
			continue
		} else {
			ac.logger.WithField("loop", "ws-health").Trace("hello'd")
			ConnectionStatus.With(prometheus.Labels{
				"outpost_name": ac.Outpost.Name,
				"outpost_type": ac.Server.Type(),
				"uuid":         ac.instanceUUID.String(),
			}).Set(1)
		}
	}
}

func (ac *APIController) startIntervalUpdater() {
	logger := ac.logger.WithField("loop", "interval-updater")
	ticker := time.NewTicker(5 * time.Minute)
	for ; true; <-ticker.C {
		logger.Debug("Running interval update")
		err := ac.OnRefresh()
		if err != nil {
			logger.WithError(err).Debug("Failed to update")
		} else {
			LastUpdate.With(prometheus.Labels{
				"outpost_name": ac.Outpost.Name,
				"outpost_type": ac.Server.Type(),
				"uuid":         ac.instanceUUID.String(),
				"version":      constants.VERSION,
				"build":        constants.BUILD("tagged"),
			}).SetToCurrentTime()
		}
	}
}

func (a *APIController) AddWSHandler(handler WSHandler) {
	a.wsHandlers = append(a.wsHandlers, handler)
}

func (a *APIController) SendWSHello(args map[string]interface{}) error {
	allArgs := a.getWebsocketPingArgs()
	for key, value := range args {
		allArgs[key] = value
	}
	aliveMsg := websocketMessage{
		Instruction: WebsocketInstructionHello,
		Args:        allArgs,
	}
	err := a.wsConn.WriteJSON(aliveMsg)
	return err
}
