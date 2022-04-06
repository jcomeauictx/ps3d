SOURCES = $(wildcard *.py)
LINT = $(SOURCES:.py=.lint)
TEST = $(SOURCES:.py=.doctest)
PYTHON ?= python3
PYLINT ?= pylint3  # may be simply `pylint`, especially on Debian 11+
export

all: lint test run
run: test.view
lint: $(LINT)
test: $(TEST)
%.lint: %.py
	$(PYLINT) $<
%.doctest: %.py
	$(PYTHON) -m doctest $<
%.mtl %.obj: ps3d.py %.ps3d
	./$+ $(@:.mtl=.obj) $(@:.obj=.mtl)
%.view: %.obj
	-cd $(<D) && timeout 10 meshlab $(<F)
view: sample/a_test.view
%.ps: %.ps3d
	-timeout 3 gs $<
ps: test.ps
.PRECIOUS: %.obj %.mtl
