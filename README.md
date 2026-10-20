# ttl2svg

Render an RDF graph as SVG. Blue ellipses are subjects (with `rdf:type` in the label), white ellipses are object-only resources, grey boxes are literals. Edge labels are prefixed predicates; literal labels keep datatype and language tags. Every SVG includes a legend of the prefixes used in the labels. Turtle and N-Triples are accepted.

## Run

Put `.ttl` or `.nt` files in `in/`, then convert all of them:

```bash
docker build -t ttl2svg .

docker run --rm \
  -v "$(pwd)/in:/data/in" \
  -v "$(pwd)/out:/data/out" \
  ttl2svg /data/in -o /data/out
```

One SVG per input file lands in `out/`. Pass a single file instead of the directory to convert just that file.

## UML mode

`--uml` draws each instance as a box (`name : Class`) with its literal values and datatypes inside. Links between instances become edges labelled with the prefixed predicate; parallel links between the same pair merge into one edge, self links stay inside the box, and literals never become nodes.

```bash
docker run --rm \
  -v "$(pwd)/in:/data/in" \
  -v "$(pwd)/out:/data/out" \
  ttl2svg /data/in -o /data/out --uml
```

`--uml` cannot be combined with `--no-literals` or `--subjects-only`.

## Hover and copy

`--interactive` adds full-value tooltips and click-to-copy. Hover a node or edge to see the full URI, literal or predicate; in UML mode the same works per header, property and value cell. Click to copy that value.

```bash
docker run --rm \
  -v "$(pwd)/in:/data/in" \
  -v "$(pwd)/out:/data/out" \
  ttl2svg /data/in -o /data/out --interactive
```

The copy script only runs when the SVG is opened directly in a browser. It is blocked in `<img>` tags and ignored by Inkscape and most other viewers; native tooltips still work there. `--interactive` cannot be combined with `--subjects-only`.

## Options

- `-o` output `.svg` file or directory (default: next to the input; a directory input defaults to a sibling `out/`)
- `--engine` `dot|fdp|sfdp|neato|twopi`
- `--no-literals` skip literal values
- `--subjects-only` list subjects of a single file with types, no rendering
- `--max-label-length` chars of a literal shown (default 40)
- `--uml` instance boxes with values inside, edges only between instances
- `--interactive` full-value hover tooltips and click-to-copy

## Test

```bash
docker run --rm -v "$(pwd):/work" -w /work --entrypoint bash ttl2svg ./test.sh
```

Writes test graphs to `out/`.

> Vibecoded by an LLM in one session. Read the script before you trust it.
