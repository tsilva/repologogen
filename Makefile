install-skill:
	python3 scripts/install_codex_skill.py

release-%:
	hatch version $*
	git add pyproject.toml
	git commit -m "chore: release $$(hatch version)"
	git push
