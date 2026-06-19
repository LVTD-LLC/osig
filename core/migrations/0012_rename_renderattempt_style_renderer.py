from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0011_renderattempt"),
    ]

    operations = [
        migrations.RenameField(
            model_name="renderattempt",
            old_name="style",
            new_name="renderer",
        ),
    ]
