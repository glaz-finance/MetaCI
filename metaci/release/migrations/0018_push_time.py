# Generated by Django 3.1.13 on 2021-07-28 20:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("release", "0017_auto_20210526_2238"),
    ]

    operations = [
        migrations.AddField(
            model_name="implementationstep",
            name="push_time",
            field=models.DateTimeField(null=True, verbose_name="push_time", blank=True),
        ),
    ]