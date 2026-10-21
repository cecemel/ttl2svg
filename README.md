# ttl2svg

Render RDF as SVG. Takes Turtle or N-Triples, one file or a directory.

In the default view, subjects are blue ellipses, resources that are only an object are white ellipses, and literals are grey boxes. Edges show the prefixed predicate. Literal labels keep datatype and language. Each graph has a legend with the prefixes used.

## run

Put files in `in/`, then:

```bash
docker build -t ttl2svg .

docker run --rm \
  -v "$(pwd)/in:/data/in" \
  -v "$(pwd)/out:/data/out" \
  ttl2svg /data/in -o /data/out
```

One SVG per input file. A single file works too. Add flags to the same command.

## options

- `-o PATH` output file or directory. Default: next to the input. A directory input writes to a sibling `out/`.
- `--engine NAME` layout: `dot` (default), `fdp`, `sfdp`, `neato`, `twopi`.
- `--no-literals` draw only resources.
- `--max-label-length N` characters of a literal in the label. Default 40.
- `--subjects-only` print the subjects and their types. No SVG. Single file only.
- `--uml` UML-like box view: instances as boxes with their values inside, edges only between instances. Not with `--no-literals` or `--subjects-only`.
- `--interactive` show the full value on hover and copy it on click. Not with `--subjects-only`.

The interactive script runs only when you open the SVG directly in a browser. In an `<img>` tag it does not run. Inkscape and most viewers ignore it. Native tooltips still work there.

## test

```bash
docker run --rm -v "$(pwd):/work" -w /work --entrypoint bash ttl2svg ./test.sh
```

Writes test graphs to `out/`.

> Vibecoded by an LLM in one session. Read the script before you trust it.
