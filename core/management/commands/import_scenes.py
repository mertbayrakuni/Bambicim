import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import Scene, Choice, ChoiceGain, Item


def slugify_like(s: str) -> str:
    # very light slug (safe for codes)
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in s).strip("-")


class Command(BaseCommand):
    help = "Import scenes from core/static/game/scenes.json into DB (idempotent and de-duped)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default="core/static/game/scenes.json",
            help="Path to scenes.json (default: core/static/game/scenes.json)",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete all Scene/Choice/ChoiceGain rows before import.",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        path = Path(opts["path"])
        if not path.exists():
            raise CommandError(f"File not found: {path}")

        data = json.loads(path.read_text(encoding="utf-8"))
        start_key = (data.get("start") or "").strip()
        raw_scenes = data.get("scenes", {})

        if opts["reset"]:
            self.stdout.write("Resetting: deleting ChoiceGain → Choice → Scene…")
            ChoiceGain.objects.all().delete()
            Choice.objects.all().delete()
            Scene.objects.all().delete()

        # 1) Upsert scenes first (by Scene.key which is the PK)
        key_map = {}
        for skey, node in raw_scenes.items():
            skey = (skey or "").strip()
            if not skey:
                raise CommandError("A scene in JSON has an empty key — please fix the JSON.")
            title = (node.get("title") or skey).strip()
            text = (node.get("text") or "").strip()

            sc, _created = Scene.objects.update_or_create(
                key=skey,
                defaults={"title": title, "text": text, "is_start": (skey == start_key)},
            )
            key_map[skey] = sc

        # 2) Nuke choices/gains globally (so re-import is deterministic)
        ChoiceGain.objects.all().delete()
        Choice.objects.all().delete()

        # 3) Recreate choices and gains
        for skey, node in raw_scenes.items():
            sc = key_map[skey]

            used_codes = set()  # track per scene to ensure uniqueness even within this import
            for idx, ch in enumerate(node.get("choices", [])):
                label = (ch.get("text") or "Continue").strip()

                base_code = slugify_like(label) or f"choice-{idx}"
                code = base_code
                # ensure unique (scene, code)
                n = 2
                while code in used_codes or Choice.objects.filter(scene=sc, code=code).exists():
                    code = f"{base_code}-{n}"
                    n += 1
                used_codes.add(code)

                tgt_key = (ch.get("target") or "").strip()
                next_scene = key_map.get(tgt_key) if tgt_key else None

                choice = Choice.objects.create(
                    scene=sc,
                    code=code,
                    label=label,
                    next_scene=next_scene,
                    order=idx,
                )

                for g in ch.get("gains", []):
                    item_slug = (g.get("item") or "").strip()
                    if not item_slug:
                        continue
                    qty = int(g.get("qty", 1))
                    item, _ = Item.objects.get_or_create(
                        slug=item_slug,
                        defaults={"name": item_slug, "emoji": "✨"},
                    )
                    ChoiceGain.objects.create(choice=choice, item=item, qty=qty)

        self.stdout.write(self.style.SUCCESS(f"Imported {len(raw_scenes)} scenes. Start='{start_key}'"))
