#!/usr/bin/env bash
# Renders spec-stress TTL files to out/ so the output can be checked visually.
# Usage: ./test.sh   (needs the tool in your PATH, or the docker image built)
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
out="$here/out"
mkdir -p "$out"

# 1. Full Turtle spec corners: prefixes/base, relative IRIs, shorthand
#    literals, datatype/language tags, multiline strings, unicode escapes,
#    collections, anonymous blank nodes.
cat > /tmp/ttl2svg-spec-stress.ttl <<'EOF'
@prefix ex: <http://example.org/vocab#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@base <http://example.org/base/> .

<doc> a ex:Doc ;
    ex:int 42 ;
    ex:decimal 3.14 ;
    ex:double 2.5E3 ;
    ex:bool true ;
    ex:lang "héllo"@nl-BE ;
    ex:typed "100"^^xsd:int ;
    ex:long """multi
line "quoted" string""" ;
    ex:unicode "tab\u0009end" ;
    ex:rel <relative-iri> ;
    ex:list ( ex:one "two" [ ex:nested ex:deep ] ( ) ) ;
    ex:props [ ex:p1 "v1"; ex:p2 [ ex:p3 "v3" ] ] ;
    ex:empty () .
EOF

# 2. Same literal value with different types: the rendered labels must differ.
cat > /tmp/ttl2svg-literal-types.ttl <<'EOF'
@prefix ex: <http://example.org/vocab#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
<s> ex:plain "100" ;
    ex:int "100"^^xsd:int ;
    ex:lang "100"@en ;
    ex:bool true ;
    ex:boolTyped "true"^^xsd:boolean ;
    ex:date "2026-01-01"^^xsd:date ;
    ex:odd "100"^^<http://example.org/ns/weird#type> ;
    ex:string "100"^^xsd:string .
EOF

# 3. N-Triples (subset of Turtle) must also render.
cat > /tmp/ttl2svg-ntest.nt <<'EOF'
<http://example.org/s1> <http://example.org/p1> "lit" .
<http://example.org/s1> <http://example.org/p2> _:b1 .
_:b1 <http://example.org/p3> <http://example.org/o1> .
EOF

if command -v docker >/dev/null && docker image inspect ttl2svg >/dev/null 2>&1; then
  runner=(docker run --rm -v "$here":/work -w /work ttl2svg)
else
  runner=(python3 "$here/visualize_ttl.py")
fi

"${runner[@]}" /tmp/ttl2svg-spec-stress.ttl -o "$out/spec-stress.svg" --max-label-length 60
"${runner[@]}" /tmp/ttl2svg-literal-types.ttl -o "$out/literal-types.svg"
"${runner[@]}" /tmp/ttl2svg-ntest.nt -o "$out/ntriples.svg"

echo "Rendered:"
echo "  $out/spec-stress.svg      check: 25 triples, collection/blank-node chains, types in labels"
echo "  $out/literal-types.svg    check: every '100' label carries a different type tag"
echo "  $out/ntriples.svg         check: 3 nodes + 2 edges, bnode drawn once"
