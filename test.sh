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

# 4. UML view: instances as boxes, typed values inside, edges only between boxes.
cat > /tmp/ttl2svg-uml.ttl <<'EOF'
@prefix ex: <http://example.org/vocab#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

ex:alice a ex:Person ;
    ex:name "Alice" ;
    ex:age "42"^^xsd:int ;
    ex:label "Alice"@en ;
    ex:knows ex:bob ;
    ex:employer ex:acme ;
    ex:worksFor ex:acme ;
    ex:memberOf ex:team1 ;
    ex:birthPlace ex:ghent ;
    ex:self ex:alice .

ex:bob a ex:Person ;
    ex:name "Bob" ;
    ex:knows ex:alice ;
    ex:worksFor ex:acme ;
    ex:memberOf ex:team1 ;
    ex:partOf ex:team1 ;
    ex:address ex:addr1 .

ex:acme a ex:Company ;
    ex:name "ACME" ;
    ex:founded "1999-01-01"^^xsd:date .

ex:team1 a ex:Team ;
    ex:name "Core" ;
    ex:lead ex:alice .

ex:addr1 ex:street "Main St" ;
    ex:city "Springfield" .
EOF

if command -v docker >/dev/null && docker image inspect ttl2svg >/dev/null 2>&1; then
  runner=(docker run --rm -v "$here":/work -w /work ttl2svg)
else
  runner=(python3 "$here/visualize_ttl.py")
fi

"${runner[@]}" /tmp/ttl2svg-spec-stress.ttl -o "$out/spec-stress.svg" --max-label-length 60
"${runner[@]}" /tmp/ttl2svg-literal-types.ttl -o "$out/literal-types.svg"
"${runner[@]}" /tmp/ttl2svg-ntest.nt -o "$out/ntriples.svg"
"${runner[@]}" /tmp/ttl2svg-uml.ttl -o "$out/uml.svg" --uml

uml="$out/uml.svg"
fail() { echo "FAIL: $*" >&2; exit 1; }
[ "$(grep -c '<g id="node' "$uml" || true)" -eq 5 ] || fail "expected 5 boxes"
[ "$(grep -c '<g id="edge' "$uml" || true)" -eq 8 ] || fail "expected 8 edges"
grep -q 'alice : Person' "$uml" || fail "missing alice box header"
grep -q '42^^xsd:int' "$uml" || fail "missing typed literal"
grep -q 'Alice@en' "$uml" || fail "missing language tag"
grep -q 'xsd:date' "$uml" || fail "missing date literal"
grep -q 'employer, worksFor' "$uml" || fail "parallel edges not merged"
grep -q 'memberOf, partOf' "$uml" || fail "parallel edges not merged"
grep -q 'ex:ghent' "$uml" || fail "object-only target should be an attribute row"
grep -q '>self<' "$uml" || fail "self reference should be an attribute row"
if grep -q 'rdf:type' "$uml"; then fail "rdf:type should not be shown"; fi
if "${runner[@]}" /tmp/ttl2svg-uml.ttl -o "$out/uml-invalid.svg" --uml --no-literals >/dev/null 2>&1; then
  fail "--uml accepted --no-literals"
fi
if "${runner[@]}" /tmp/ttl2svg-uml.ttl -o "$out/uml-invalid.svg" --uml --subjects-only >/dev/null 2>&1; then
  fail "--uml accepted --subjects-only"
fi

batch="$out/.tmp-batch"
trap 'rm -rf "$batch"' EXIT
rm -rf "$batch"
mkdir -p "$batch/in"
cp /tmp/ttl2svg-uml.ttl "$batch/in/uml.ttl"
cp /tmp/ttl2svg-ntest.nt "$batch/in/ntriples.nt"
echo "ignore me" > "$batch/in/notes.txt"
"${runner[@]}" "$batch/in" -o "$batch/out" --uml
[ -f "$batch/out/uml.svg" ] || fail "batch did not render uml.ttl"
[ -f "$batch/out/ntriples.svg" ] || fail "batch did not render ntriples.nt"
[ ! -f "$batch/out/notes.svg" ] || fail "batch converted a non-RDF file"
mkdir -p "$batch/single"
"${runner[@]}" /tmp/ttl2svg-ntest.nt -o "$batch/single"
[ -f "$batch/single/ttl2svg-ntest.svg" ] || fail "single file did not render into output dir"

echo "Rendered:"
echo "  $out/spec-stress.svg      check: 25 triples, collection/blank-node chains, types in labels"
echo "  $out/literal-types.svg    check: every '100' label carries a different type tag"
echo "  $out/ntriples.svg         check: 3 nodes + 2 edges, bnode drawn once"
echo "  $out/uml.svg              check: 5 boxes, 8 edges, typed values inside, merged labels"
echo "  batch run                 check: both RDF files converted, notes.txt ignored, single file into output dir"
