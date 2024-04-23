# Generated by Django 3.2.8 on 2021-10-10 16:26

import django.db.models.deletion
from django.apps.registry import Apps
from django.db import migrations, models

import authentik.lib.validators


def set_managed_flag(apps: Apps, schema_editor):
    LDAPPropertyMapping = apps.get_model("authentik_sources_ldap", "LDAPPropertyMapping")
    db_alias = schema_editor.connection.alias
    field_to_uid = {
        "name": "goauthentik.io/sources/ldap/default-name",
        "email": "goauthentik.io/sources/ldap/default-mail",
        "username": "goauthentik.io/sources/ldap/ms-samaccountname",
        "attributes.upn": "goauthentik.io/sources/ldap/ms-userprincipalname",
        "first_name": "goauthentik.io/sources/ldap/ms-givenName",
        "last_name": "goauthentik.io/sources/ldap/ms-sn",
    }
    for mapping in LDAPPropertyMapping.objects.using(db_alias).filter(
        name__startswith="Autogenerated "
    ):
        mapping.managed = field_to_uid.get(mapping.object_field)
        mapping.save()


def set_default_group_mappings(apps: Apps, schema_editor):
    LDAPPropertyMapping = apps.get_model("authentik_sources_ldap", "LDAPPropertyMapping")
    LDAPSource = apps.get_model("authentik_sources_ldap", "LDAPSource")
    db_alias = schema_editor.connection.alias

    for source in LDAPSource.objects.using(db_alias).all():
        if source.property_mappings_group.exists():
            continue
        source.property_mappings_group.set(
            LDAPPropertyMapping.objects.using(db_alias).filter(
                managed="goauthentik.io/sources/ldap/default-name"
            )
        )
        source.save()


class Migration(migrations.Migration):
    replaces = [
        ("authentik_sources_ldap", "0001_initial"),
        ("authentik_sources_ldap", "0002_ldapsource_sync_users"),
        ("authentik_sources_ldap", "0003_default_ldap_property_mappings"),
        ("authentik_sources_ldap", "0004_auto_20200524_1146"),
        ("authentik_sources_ldap", "0005_auto_20200913_1947"),
        ("authentik_sources_ldap", "0006_auto_20200915_1919"),
        ("authentik_sources_ldap", "0007_ldapsource_sync_users_password"),
        ("authentik_sources_ldap", "0008_managed"),
        ("authentik_sources_ldap", "0009_auto_20210204_1834"),
        ("authentik_sources_ldap", "0010_auto_20210205_1027"),
        ("authentik_sources_ldap", "0011_ldapsource_property_mappings_group"),
        ("authentik_sources_ldap", "0012_auto_20210812_1703"),
    ]

    initial = True

    dependencies = [
        ("authentik_core", "0001_initial"),
        ("authentik_core", "0017_managed"),
    ]

    operations = [
        migrations.CreateModel(
            name="LDAPPropertyMapping",
            fields=[
                (
                    "propertymapping_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="authentik_core.propertymapping",
                    ),
                ),
                ("object_field", models.TextField()),
            ],
            options={
                "verbose_name": "LDAP Property Mapping",
                "verbose_name_plural": "LDAP Property Mappings",
            },
            bases=("authentik_core.propertymapping",),
        ),
        migrations.CreateModel(
            name="LDAPSource",
            fields=[
                (
                    "source_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="authentik_core.source",
                    ),
                ),
                (
                    "server_uri",
                    models.TextField(
                        validators=[
                            authentik.lib.validators.DomainlessURLValidator(
                                schemes=["ldap", "ldaps"]
                            )
                        ],
                        verbose_name="Server URI",
                    ),
                ),
                ("bind_cn", models.TextField(verbose_name="Bind CN")),
                ("bind_password", models.TextField()),
                ("start_tls", models.BooleanField(default=False, verbose_name="Enable Start TLS")),
                ("base_dn", models.TextField(verbose_name="Base DN")),
                (
                    "additional_user_dn",
                    models.TextField(
                        blank=True,
                        help_text="Prepended to Base DN for User-queries.",
                        verbose_name="Addition User DN",
                    ),
                ),
                (
                    "additional_group_dn",
                    models.TextField(
                        blank=True,
                        help_text="Prepended to Base DN for Group-queries.",
                        verbose_name="Addition Group DN",
                    ),
                ),
                (
                    "user_object_filter",
                    models.TextField(
                        default="(objectCategory=Person)",
                        help_text="Consider Objects matching this filter to be Users.",
                    ),
                ),
                (
                    "user_group_membership_field",
                    models.TextField(
                        default="memberOf", help_text="Field which contains Groups of user."
                    ),
                ),
                (
                    "group_object_filter",
                    models.TextField(
                        default="(objectCategory=Group)",
                        help_text="Consider Objects matching this filter to be Groups.",
                    ),
                ),
                (
                    "object_uniqueness_field",
                    models.TextField(
                        default="objectSid", help_text="Field which contains a unique Identifier."
                    ),
                ),
                ("sync_groups", models.BooleanField(default=True)),
                (
                    "sync_parent_group",
                    models.ForeignKey(
                        blank=True,
                        default=None,
                        null=True,
                        on_delete=django.db.models.deletion.SET_DEFAULT,
                        to="authentik_core.group",
                    ),
                ),
                ("sync_users", models.BooleanField(default=True)),
                (
                    "sync_users_password",
                    models.BooleanField(
                        default=True,
                        help_text=(
                            "When a user changes their password, sync it back to LDAP. This can"
                            " only be enabled on a single LDAP source."
                        ),
                        unique=True,
                    ),
                ),
            ],
            options={
                "verbose_name": "LDAP Source",
                "verbose_name_plural": "LDAP Sources",
            },
            bases=("authentik_core.source",),
        ),
        migrations.RunPython(
            code=set_managed_flag,
        ),
        migrations.RemoveField(
            model_name="ldapsource",
            name="user_group_membership_field",
        ),
        migrations.AddField(
            model_name="ldapsource",
            name="group_membership_field",
            field=models.TextField(
                default="member", help_text="Field which contains members of a group."
            ),
        ),
        migrations.AlterField(
            model_name="ldapsource",
            name="group_object_filter",
            field=models.TextField(
                default="(objectClass=group)",
                help_text="Consider Objects matching this filter to be Groups.",
            ),
        ),
        migrations.AlterField(
            model_name="ldapsource",
            name="user_object_filter",
            field=models.TextField(
                default="(objectClass=person)",
                help_text="Consider Objects matching this filter to be Users.",
            ),
        ),
        migrations.AddField(
            model_name="ldapsource",
            name="property_mappings_group",
            field=models.ManyToManyField(
                blank=True,
                default=None,
                help_text="Property mappings used for group creation/updating.",
                to="authentik_core.PropertyMapping",
            ),
        ),
        migrations.RunPython(
            code=set_default_group_mappings,
        ),
        migrations.AlterField(
            model_name="ldapsource",
            name="bind_cn",
            field=models.TextField(blank=True, verbose_name="Bind CN"),
        ),
        migrations.AlterField(
            model_name="ldapsource",
            name="bind_password",
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name="ldapsource",
            name="sync_users_password",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "When a user changes their password, sync it back to LDAP. This can only be"
                    " enabled on a single LDAP source."
                ),
            ),
        ),
    ]
