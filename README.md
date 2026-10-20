# ttl2svg

Renders a TTL file as an SVG graph. URIs become ellipses (blue = subject, with `rdf:type` in the label), literals become grey boxes, edge labels are the predicates (prefixed).

## Run

```bash
docker build -t ttl2svg .

docker run --rm \
  -v "$(pwd)/in:/data/in" \
  -v "$(pwd)/out:/data/out" \
  ttl2svg /data/in/example.ttl -o /data/out/graph.svg
```

The svg ends up in `out/`. Put your `.ttl` in `in/`.

## Test

```bash
docker run --rm -v "$(pwd):/work" -w /work --entrypoint bash ttl2svg ./test.sh
```

Writes spec-stress graphs to `out/` to check visually.

## Options

- `-o` output path (default: next to the ttl)
- `--engine` `dot|fdp|sfdp|neato|twopi`
- `--no-literals` skip literal values
- `--subjects-only` list subjects with types, no rendering
- `--max-label-length 40` chars of a literal shown
