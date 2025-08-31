import json
from pathlib import Path
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from core.models import Scene, Choice, ChoiceGain, Item


class Command(BaseCommand):
    help = "Import scenes from core/static/game/scenes.json into DB"

    def add_arguments(self, parser):
        parser.add_argument("--wipe", action="store_true", help="Delete existing scenes/choices/gains first")

    def handle(self, *args, **opts):
        json_path = Path(__file__).resolve().parents[3] / "core" / "static" / "game" / "scenes.json"
        data = json.loads(json_path.read_text(encoding="utf-8"))
        scenes = data.get("scenes", {})
        start_key = data.get("start")

        with transaction.atomic():
            if opts["wipe"]:
                ChoiceGain.objects.all().delete()
                Choice.objects.all().delete()
                Scene.objects.all().delete()

            # 1) create all scenes first
            db_scenes = {}
            for key, node in scenes.items():
                sc, _ = Scene.objects.get_or_create(
                    key=key,
                    defaults={"title": node.get("title", ""), "text": node.get("text", ""),
                              "is_start": key == start_key}
                )
                # keep latest copy of text/title
                sc.title = node.get("title", "")
                sc.text = node.get("text", "")
                sc.is_start = (key == start_key)
                sc.save()
                db_scenes[key] = sc

            # 2) choices + gains
            for key, node in scenes.items():
                sc = db_scenes[key]
                # wipe scene’s choices to avoid duplicates
                sc.choices.all().delete()

                for idx, ch in enumerate(node.get("choices", [])):
                    label = ch.get("label") or ch.get("text") or "Continue"
                    code = slugify(label) or f"choice-{idx + 1}"
                    next_key = ch.get("next") or ch.get("target")
                    next_sc = db_scenes.get(next_key) if next_key else None

                    choice = Choice.objects.create(
                        scene=sc, code=code, label=label, next_scene=next_sc, order=idx
                    )

                    gains = ch.get("gain") or ch.get("gains") or []
                    if isinstance(gains, list):
                        for g in gains:
                            if isinstance(g, str):
                                slug, qty = g, 1
                            else:
                                slug, qty = (g.get("slug") or g.get("item")), int(g.get("qty", 1))
                            if not slug:
                                continue
                            item, _ = Item.objects.get_or_create(slug=slug,
                                                                 defaults={"name": slug.replace("-", " ").title()})
                            ChoiceGain.objects.create(choice=choice, item=item, qty=qty)

        self.stdout.write(self.style.SUCCESS("Scenes imported successfully."))
