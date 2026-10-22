.PHONY: build build-all

build:
	python3 scripts/build.py --year "$(YEAR)" --persona "$(PERSONA)"

build-all:
	python3 scripts/build.py --all
