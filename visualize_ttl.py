#!/usr/bin/env python3
"""
Render an RDF TTL file (for example a cleanup backup from task 2) as an SVG
graph. URIs become ellipses, literals become boxes, predicates are the edge
labels. Uses rdflib to parse and graphviz to render. See README.md.
"""

import argparse
import re
import sys
from pathlib import Path

import graphviz
import rdflib
from rdflib import Graph, URIRef
from rdflib.namespace import Namespace, RDF

PREFIXES = {
    "rdf": RDF,
    "rdfs": rdflib.RDFS,
    "xsd": rdflib.XSD,
    "dct": rdflib.DCTERMS,
    "prov": rdflib.PROV,
    "skos": rdflib.SKOS,
    "foaf": rdflib.FOAF,
    "schema": rdflib.SDO,
    "dbo": Namespace("http://dbpedia.org/ontology/"),
    "dbr": Namespace("http://dbpedia.org/resource/"),
    "nie": Namespace("http://www.semanticdesktop.org/ontologies/2007/01/19/nie#"),
    "nfo": Namespace("http://www.semanticdesktop.org/ontologies/2007/03/22/nfo#"),
    "mu": Namespace("http://mu.semte.ch/vocabularies/core/"),
    "ext": Namespace("http://mu.semte.ch/vocabularies/ext/"),
    "adms": Namespace("http://www.w3.org/ns/adms#"),
    "pav": Namespace("http://purl.org/pav/"),
    "meb": Namespace("http://rdf.myexperiment.org/ontologies/base/"),
    "task": Namespace("http://redpencil.data.gift/vocabularies/tasks/"),
    "cogs": Namespace("http://vocab.deri.ie/cogs#"),
    "oscaf": Namespace("http://oscaf.sourceforge.net/ndo.html#"),
    "sec": Namespace("http://lblod.data.gift/vocabularies/security/"),
}

UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)


def squeeze(text):
    """Compress every uuid inside a string to its first 8 characters."""
    return UUID_RE.sub(lambda match: match.group(0)[:8] + "...", text)


def uri_label(manager, uri):
    try:
        prefix, _, local = manager.compute_qname(URIRef(uri), generate=False)
        label = f"{prefix}:{local}"
        if len(label) <= 48:
            return squeeze(label)
    except Exception:
        pass
    if not uri.startswith("http"):
        return squeeze(uri)
    path = uri.split("//", 1)[1]
    parts = [part for part in path.split("/") if part]
    tail = "/".join(parts[-2:]) if len(parts) > 1 else parts[-1]
    return squeeze(tail)


def literal_label(value, max_length, manager):
    text = str(value).replace("\n", "\\n")
    if len(text) > max_length:
        text = text[: max_length - 3] + "..."
    text = squeeze(text)
    tag = ""
    if value.language:
        tag = f"@{value.language}"
    elif value.datatype and str(value.datatype) not in (
        "http://www.w3.org/2001/XMLSchema#string",
        "http://www.w3.org/1999/02/22-rdf-syntax-ns#langString",
    ):
        try:
            prefix, _, local = manager.compute_qname(value.datatype, generate=False)
            tag = f"^^{prefix}:{local}"
        except Exception:
            tag = f"^^<{str(value.datatype).split('//', 1)[-1]}>"
    return text + tag


def parse_ttl(ttl_path):
    graph = Graph()
    graph.parse(ttl_path, format="turtle")
    for prefix, namespace in PREFIXES.items():
        graph.namespace_manager.bind(prefix, namespace, override=True, replace=True)
    return graph


SUBJECT_FILL = "#d5e8f8"
LITERAL_FILL = "#f5f5f5"


def build_graph(ttl_path, engine, show_literals, max_length):
    graph = parse_ttl(ttl_path)
    manager = graph.namespace_manager

    subjects = set(graph.subjects())

    def types_of(term):
        return sorted(uri_label(manager, str(rdf_type))
                      for rdf_type in graph.objects(term, RDF.type))

    dot = graphviz.Digraph(name=Path(ttl_path).stem, format="svg", engine=engine)
    dot.attr(rankdir="LR", ranksep="1", nodesep="0.4", bgcolor="white")
    dot.attr("graph", label=f"{Path(ttl_path).name}: {len(graph)} triples"
                             f" | blue nodes are the subjects")
    dot.attr("graph", labelloc="t")
    dot.attr("node", fontsize="11")
    dot.attr("edge", fontsize="9", color="#555555")

    node_ids = {}

    def node_id(term):
        if term not in node_ids:
            node_ids[term] = f"n{len(node_ids)}"
            draw_node(term)
        return node_ids[term]

    def draw_node(term):
        if isinstance(term, rdflib.Literal):
            label = literal_label(term, max_length, manager)
            dot.node(node_ids[term], shape="box", style="filled",
                     fillcolor=LITERAL_FILL, label=label)
            return
        if isinstance(term, rdflib.BNode):
            label = squeeze(str(term))
        else:
            label = uri_label(manager, str(term))
        if term in subjects:
            node_types = types_of(term)
            if node_types:
                label += "\n" + ", ".join(node_types)
            dot.node(node_ids[term], shape="ellipse", style="filled",
                     fillcolor=SUBJECT_FILL, label=label)
        else:
            dot.node(node_ids[term], shape="ellipse", label=label)

    for subject, predicate, obj in graph:
        if predicate == RDF.type:
            continue
        if isinstance(obj, rdflib.Literal) and not show_literals:
            node_id(subject)
            continue
        node_id(subject)
        node_id(obj)
        dot.edge(node_ids[subject], node_ids[obj],
                 label=uri_label(manager, str(predicate)))

    return dot


def main():
    args = parse_args()
    if not Path(args.ttl).is_file():
        sys.exit(f"No such file: {args.ttl}")

    if args.subjects_only:
        graph = parse_ttl(args.ttl)
        manager = graph.namespace_manager
        for subject in sorted(set(graph.subjects()), key=str):
            types = sorted(uri_label(manager, str(rdf_type))
                           for rdf_type in graph.objects(subject, RDF.type))
            print(str(subject) + (("\t" + ", ".join(types)) if types else ""))
        return

    output = Path(args.output) if args.output else Path(args.ttl).with_suffix(".svg")

    dot = build_graph(args.ttl, args.engine, not args.no_literals, args.max_label_length)
    rendered = dot.render(outfile=str(output))
    print(f"Wrote {rendered}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Render a TTL file as an SVG graph."
    )
    parser.add_argument("ttl", help="path to the .ttl file to render")
    parser.add_argument("-o", "--output", help="output .svg path (default: next to the ttl)")
    parser.add_argument("--engine", default="dot",
                        help="graphviz layout engine: dot, fdp, sfdp, neato, twopi (default: dot)")
    parser.add_argument("--no-literals", action="store_true",
                        help="only draw the resources, skip literal values")
    parser.add_argument("--subjects-only", action="store_true",
                        help="print the distinct subjects of the ttl, no rendering")
    parser.add_argument("--max-label-length", type=int, default=40,
                        help="max characters of a literal shown (default: 40)")
    return parser.parse_args()


if __name__ == "__main__":
    main()
