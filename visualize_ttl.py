#!/usr/bin/env python3
"""
Render RDF TTL/N-Triples files (for example cleanup backups from task 2) as
SVG graphs. A single file or a directory can be passed; directories are
converted file by file. URIs become ellipses, literals become boxes, predicates
are the edge labels. With --uml, instances become boxes with their values
inside and edges only between instances. Uses rdflib to parse and graphviz to
render. See README.md.
"""

import argparse
import html
import re
import sys
from pathlib import Path

import graphviz
import rdflib
from rdflib import BNode, Graph, Literal, URIRef
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


def local_name(manager, term):
    """Return the local part of a URI, or the short id of a blank node."""
    if isinstance(term, BNode):
        return squeeze(str(term))
    uri = str(term)
    try:
        _, _, local = manager.compute_qname(URIRef(uri), generate=False)
        if local:
            return squeeze(local)
    except Exception:
        pass
    if not uri.startswith("http"):
        return squeeze(uri)
    tail = uri.rstrip("/").rsplit("/", 1)[-1].rsplit("#", 1)[-1]
    return squeeze(tail or uri)


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


def uml_label(header, rows):
    def escape(text):
        return html.escape(text, quote=False)

    parts = [
        '<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="4">',
        f'<TR><TD COLSPAN="2" BGCOLOR="{SUBJECT_FILL}" ALIGN="CENTER" '
        f'SIDES="B" BORDER="1"><B>{escape(header)}</B></TD></TR>',
    ]
    if rows:
        for prop, value in rows:
            parts.append(
                f'<TR><TD ALIGN="LEFT" BALIGN="LEFT">{escape(prop)}</TD>'
                f'<TD ALIGN="LEFT" BALIGN="LEFT">{escape(value)}</TD></TR>'
            )
    parts.append("</TABLE>")
    return "<" + "".join(parts) + ">"


def build_uml_graph(ttl_path, engine, max_length):
    graph = parse_ttl(ttl_path)
    manager = graph.namespace_manager

    instance_types = {}
    for subject, obj in graph.subject_objects(RDF.type):
        if isinstance(obj, URIRef):
            instance_types.setdefault(subject, set()).add(obj)

    box_terms = set(graph.subjects())
    rows = {term: [] for term in box_terms}
    edges = {}

    for subject in box_terms:
        properties = {}
        for predicate, obj in graph.predicate_objects(subject):
            if predicate == RDF.type:
                continue
            properties.setdefault(predicate, []).append(obj)

        for predicate in sorted(properties,
                                key=lambda p: (local_name(manager, p), str(p))):
            prop = local_name(manager, predicate)
            values = properties[predicate]
            literals = sorted(
                (value for value in values if isinstance(value, Literal)),
                key=lambda value: (str(value), str(value.datatype or ""),
                                   value.language or ""),
            )
            if literals:
                text = ", ".join(literal_label(value, max_length, manager)
                                 for value in literals)
                rows[subject].append((prop, text))
            objects = sorted((value for value in values
                              if not isinstance(value, Literal)), key=str)
            for obj in objects:
                if obj == subject:
                    rows[subject].append((prop, local_name(manager, obj)))
                elif obj in box_terms:
                    edges.setdefault((subject, obj), set()).add(prop)
                else:
                    rows[subject].append((prop, uri_label(manager, str(obj))))

    for term in rows:
        rows[term].sort()

    dot = graphviz.Digraph(name=Path(ttl_path).stem, format="svg", engine=engine)
    dot.attr(rankdir="LR", ranksep="1", nodesep="0.4", bgcolor="white")
    dot.attr("graph", label=f"{Path(ttl_path).name}: {len(graph)} triples | UML view")
    dot.attr("graph", labelloc="t")
    dot.attr("node", fontsize="11")
    dot.attr("edge", fontsize="9", color="#555555")

    node_ids = {}
    for term in sorted(box_terms, key=lambda t: (local_name(manager, t), str(t))):
        node_ids[term] = f"u{len(node_ids)}"
        header = local_name(manager, term)
        types = sorted(local_name(manager, rdf_type)
                       for rdf_type in instance_types.get(term, ()))
        if types:
            header += " : " + ", ".join(types)
        dot.node(node_ids[term], shape="box", style="filled", fillcolor="white",
                 color="#555555", label=uml_label(header, rows[term]))

    for subject, obj in sorted(edges, key=lambda pair: (str(pair[0]), str(pair[1]))):
        label = ", ".join(sorted(edges[(subject, obj)]))
        dot.edge(node_ids[subject], node_ids[obj], label=label)

    return dot


RDF_SUFFIXES = {".ttl", ".nt", ".turtle"}


def rdf_files(directory):
    return sorted(path for path in directory.iterdir()
                  if path.is_file() and path.suffix.lower() in RDF_SUFFIXES)


def print_subjects(ttl_path):
    graph = parse_ttl(ttl_path)
    manager = graph.namespace_manager
    for subject in sorted(set(graph.subjects()), key=str):
        types = sorted(uri_label(manager, str(rdf_type))
                       for rdf_type in graph.objects(subject, RDF.type))
        print(str(subject) + (("\t" + ", ".join(types)) if types else ""))


def render_file(ttl_path, output_path, args):
    if args.uml:
        dot = build_uml_graph(ttl_path, args.engine, args.max_label_length)
    else:
        dot = build_graph(ttl_path, args.engine, not args.no_literals,
                          args.max_label_length)
    rendered = dot.render(outfile=str(output_path))
    print(f"Wrote {rendered}")


def output_directory(input_dir, output):
    if output:
        out = Path(output)
        if out.exists() and not out.is_dir():
            sys.exit(f"Output must be a directory: {out}")
    else:
        out = input_dir.parent / "out"
    out.mkdir(parents=True, exist_ok=True)
    return out


def output_file(input_file, output):
    if output:
        out = Path(output)
        if out.is_dir():
            return out / input_file.with_suffix(".svg").name
        return out
    return input_file.with_suffix(".svg")


def main():
    args = parse_args()
    if args.uml and args.no_literals:
        sys.exit("--uml cannot be combined with --no-literals")
    if args.uml and args.subjects_only:
        sys.exit("--uml cannot be combined with --subjects-only")

    input_path = Path(args.ttl)
    if not input_path.exists():
        sys.exit(f"No such file or directory: {input_path}")

    if args.subjects_only:
        if input_path.is_dir():
            sys.exit("--subjects-only needs a single file")
        print_subjects(input_path)
        return

    if input_path.is_dir():
        files = rdf_files(input_path)
        if not files:
            sys.exit(f"No .ttl, .nt or .turtle files in {input_path}")
        out_dir = output_directory(input_path, args.output)
        failures = 0
        for path in files:
            try:
                render_file(path, out_dir / path.with_suffix(".svg").name, args)
            except Exception as exc:
                print(f"Failed {path}: {exc}", file=sys.stderr)
                failures += 1
        if failures:
            sys.exit(1)
        return

    render_file(input_path, output_file(input_path, args.output), args)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Render RDF files as SVG graphs."
    )
    parser.add_argument("ttl", help="RDF file to render, or a directory of .ttl/.nt files")
    parser.add_argument("-o", "--output",
                        help="output .svg path or directory (default: next to the input)")
    parser.add_argument("--engine", default="dot",
                        help="graphviz layout engine: dot, fdp, sfdp, neato, twopi (default: dot)")
    parser.add_argument("--no-literals", action="store_true",
                        help="only draw the resources, skip literal values")
    parser.add_argument("--subjects-only", action="store_true",
                        help="print the distinct subjects of the ttl, no rendering")
    parser.add_argument("--max-label-length", type=int, default=40,
                        help="max characters of a literal shown (default: 40)")
    parser.add_argument("--uml", action="store_true",
                        help="UML view: instances as boxes with their values, "
                             "edges only between instances")
    return parser.parse_args()


if __name__ == "__main__":
    main()
