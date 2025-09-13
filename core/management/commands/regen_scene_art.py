from django.core.management.base import BaseCommand, CommandError

from core.art import generate_pixel_art, _prompt_for
from core.models import Scene, SceneArt


class Command(BaseCommand):
    help = "Regenerate pixel art for one or more scenes (synchronously)."

    def add_arguments(self, parser):
        parser.add_argument("keys", nargs="*", help="Scene keys (slug). Leave empty to use --all.")
        parser.add_argument("--all", action="store_true", help="Regenerate for all scenes.")
        parser.add_argument("--force", action="store_true", help="Regenerate even if status is ready.")

    def handle(self, *args, **opts):
        if not opts["keys"] and not opts["all"]:
            raise CommandError("Provide scene keys or use --all")

        if opts["all"]:
            keys = list(Scene.objects.values_list("key", flat=True))
        else:
            keys = opts["keys"]

        if not keys:
            self.stdout.write(self.style.WARNING("No scene keys to process."))
            return

        for key in keys:
            sc = Scene.objects.filter(key=key).first()
            title = sc.title if sc else key
            text = sc.text if sc else ""

            row = SceneArt.objects.filter(key=key).first()
            if row and row.status == "ready" and not opts["force"]:
                self.stdout.write(f"skip {key} (ready)")
                continue

            prompt = _prompt_for(key, title, text)
            data = generate_pixel_art(prompt)
            SceneArt.objects.update_or_create(
                key=key,
                defaults={"prompt": prompt, "status": "ready", "image_webp": data},
            )
            self.stdout.write(self.style.SUCCESS(f"generated {key}"))
