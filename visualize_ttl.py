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


def prefixed_label(manager, term):
    """Return prefix:local for a URI, keeping the prefix even for long names."""
    try:
        prefix, _, local = manager.compute_qname(URIRef(str(term)), generate=False)
        return squeeze(f"{prefix}:{local}")
    except Exception:
        return uri_label(manager, str(term))


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


def literal_tooltip(value):
    text = str(value)
    if value.language:
        return f'"{text}"@{value.language}'
    if value.datatype and str(value.datatype) not in (
        "http://www.w3.org/2001/XMLSchema#string",
        "http://www.w3.org/1999/02/22-rdf-syntax-ns#langString",
    ):
        return f'"{text}"^^<{value.datatype}>'
    return text


def term_tooltip(term):
    if isinstance(term, Literal):
        return literal_tooltip(term)
    if isinstance(term, BNode):
        return "_:" + str(term)
    return str(term)


def prefix_legend(dot, manager):
    bindings = dict(manager.namespaces())
    used = set()
    for match in re.finditer(r"(?<![\w])([A-Za-z][A-Za-z0-9_.-]*):", dot.source):
        prefix = match.group(1)
        if prefix in bindings:
            used.add(prefix)
    return [(prefix, bindings[prefix]) for prefix in sorted(used)]


def graph_label(title, prefixes):
    def escape(text):
        return html.escape(text, quote=False)

    rows = [f'<TR><TD COLSPAN="2" ALIGN="LEFT"><B>{escape(title)}</B></TD></TR>']
    if prefixes:
        rows.append('<TR><TD COLSPAN="2" ALIGN="LEFT">prefixes:</TD></TR>')
        for prefix, namespace in prefixes:
            rows.append(f'<TR><TD ALIGN="LEFT">{escape(prefix)}</TD>'
                        f'<TD ALIGN="LEFT">= {escape(namespace)}</TD></TR>')
    table = ('<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="1">'
             + "".join(rows) + "</TABLE>")
    return "<" + table + ">"


def parse_ttl(ttl_path):
    graph = Graph()
    graph.parse(ttl_path, format="turtle")
    for prefix, namespace in PREFIXES.items():
        graph.namespace_manager.bind(prefix, namespace, override=True, replace=True)
    return graph


SUBJECT_FILL = "#d5e8f8"
LITERAL_FILL = "#f5f5f5"


def build_graph(ttl_path, engine, show_literals, max_length, interactive=False):
    graph = parse_ttl(ttl_path)
    manager = graph.namespace_manager

    subjects = set(graph.subjects())

    def types_of(term):
        return sorted(uri_label(manager, str(rdf_type))
                      for rdf_type in graph.objects(term, RDF.type))

    dot = graphviz.Digraph(name=Path(ttl_path).stem, format="svg", engine=engine)
    dot.attr(rankdir="LR", ranksep="1", nodesep="0.4", bgcolor="white")
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
            attrs = dict(shape="box", style="filled", fillcolor=LITERAL_FILL,
                         label=literal_label(term, max_length, manager))
        else:
            if isinstance(term, rdflib.BNode):
                label = squeeze(str(term))
            else:
                label = uri_label(manager, str(term))
            if term in subjects:
                node_types = types_of(term)
                if node_types:
                    label += "\n" + ", ".join(node_types)
                attrs = dict(shape="ellipse", style="filled",
                             fillcolor=SUBJECT_FILL, label=label)
            else:
                attrs = dict(shape="ellipse", label=label)
        if interactive:
            attrs["tooltip"] = term_tooltip(term)
        dot.node(node_ids[term], **attrs)

    for subject, predicate, obj in graph:
        if predicate == RDF.type:
            continue
        if isinstance(obj, rdflib.Literal) and not show_literals:
            node_id(subject)
            continue
        node_id(subject)
        node_id(obj)
        attrs = dict(label=uri_label(manager, str(predicate)))
        if interactive:
            attrs["tooltip"] = str(predicate)
            attrs["labeltooltip"] = str(predicate)
        dot.edge(node_ids[subject], node_ids[obj], **attrs)

    title = f"{Path(ttl_path).name}: {len(graph)} triples | blue nodes are the subjects"
    dot.attr("graph", label=graph_label(title, prefix_legend(dot, manager)))
    return dot


def uml_label(header, header_tooltip, rows, interactive):
    def escape(text):
        return html.escape(text, quote=False)

    def attrs(tooltip):
        if not interactive:
            return ""
        tooltip = html.escape(tooltip, quote=True).replace("\n", "&#10;")
        return f' HREF="#copy" TOOLTIP="{tooltip}"'

    parts = [
        '<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="4">',
        f'<TR><TD COLSPAN="2" BGCOLOR="{SUBJECT_FILL}" ALIGN="CENTER" '
        f'SIDES="B" BORDER="1"{attrs(header_tooltip)}>'
        f'<B>{escape(header)}</B></TD></TR>',
    ]
    if rows:
        for prop, value, prop_tooltip, value_tooltip in rows:
            parts.append(
                f'<TR><TD ALIGN="LEFT" BALIGN="LEFT"{attrs(prop_tooltip)}>'
                f'{escape(prop)}</TD>'
                f'<TD ALIGN="LEFT" BALIGN="LEFT"{attrs(value_tooltip)}>'
                f'{escape(value)}</TD></TR>'
            )
    parts.append("</TABLE>")
    return "<" + "".join(parts) + ">"


def build_uml_graph(ttl_path, engine, max_length, interactive=False):
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
                full = ", ".join(literal_tooltip(value) for value in literals)
                rows[subject].append((prop, text, str(predicate), full))
            objects = sorted((value for value in values
                              if not isinstance(value, Literal)), key=str)
            for obj in objects:
                if obj == subject:
                    rows[subject].append((prop, local_name(manager, obj),
                                          str(predicate), term_tooltip(obj)))
                elif obj in box_terms:
                    edges.setdefault((subject, obj), {})[predicate] = \
                        prefixed_label(manager, predicate)
                else:
                    rows[subject].append((prop, uri_label(manager, str(obj)),
                                          str(predicate), str(obj)))

    for term in rows:
        rows[term].sort()

    dot = graphviz.Digraph(name=Path(ttl_path).stem, format="svg", engine=engine)
    dot.attr(rankdir="LR", ranksep="1", nodesep="0.4", bgcolor="white")
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
        attrs = dict(shape="box", style="filled", fillcolor="white",
                     color="#555555",
                     label=uml_label(header, term_tooltip(term), rows[term],
                                     interactive))
        if interactive:
            attrs["tooltip"] = term_tooltip(term)
        dot.node(node_ids[term], **attrs)

    for subject, obj in sorted(edges, key=lambda pair: (str(pair[0]), str(pair[1]))):
        predicates = edges[(subject, obj)]
        label = ", ".join(sorted(set(predicates.values())))
        attrs = dict(label=label)
        if interactive:
            tooltip = "\n".join(sorted(str(p) for p in predicates))
            attrs["tooltip"] = tooltip
            attrs["labeltooltip"] = tooltip
        dot.edge(node_ids[subject], node_ids[obj], **attrs)

    title = f"{Path(ttl_path).name}: {len(graph)} triples | UML-like box view"
    dot.attr("graph", label=graph_label(title, prefix_legend(dot, manager)))
    return dot


INTERACTIVE_SNIPPET = '''<foreignObject x="0" y="0" width="1" height="1" style="opacity:0;pointer-events:none">
<textarea xmlns="http://www.w3.org/1999/xhtml" id="ttl2svg-copy" readonly="readonly"></textarea>
</foreignObject>
<script type="text/javascript"><![CDATA[
(function () {
  var svg = (document.currentScript && document.currentScript.parentNode) ||
            document.documentElement;
  var XLINK = "http://www.w3.org/1999/xlink";

  function anchorTitle(el) {
    while (el && el !== svg) {
      if (el.tagName && el.tagName.toLowerCase() === "a") {
        var title = el.getAttributeNS(XLINK, "title") ||
                    el.getAttribute("xlink:title");
        if (title) return title;
      }
      el = el.parentNode;
    }
    return null;
  }

  function groupAnchorTitle(el) {
    while (el && el !== svg) {
      if (el.tagName && el.tagName.toLowerCase() === "g") {
        var cls = el.getAttribute("class") || "";
        if (cls === "node" || cls === "edge") {
          var anchors = el.getElementsByTagName("a");
          for (var i = 0; i < anchors.length; i++) {
            var title = anchors[i].getAttributeNS(XLINK, "title") ||
                        anchors[i].getAttribute("xlink:title");
            if (title) return title;
          }
        }
      }
      el = el.parentNode;
    }
    return null;
  }

  function groupTitle(el) {
    while (el && el !== svg) {
      if (el.tagName && el.tagName.toLowerCase() === "g") {
        var cls = el.getAttribute("class") || "";
        if (cls === "node" || cls === "edge") {
          for (var i = 0; i < el.childNodes.length; i++) {
            var child = el.childNodes[i];
            if (child.nodeType === 1 &&
                child.tagName.toLowerCase() === "title") {
              return child.textContent;
            }
          }
        }
      }
      el = el.parentNode;
    }
    return null;
  }

  function fallback(text) {
    var helper = svg.querySelector("textarea");
    if (!helper) { window.prompt("Copy:", text); return; }
    helper.value = text;
    helper.focus({ preventScroll: true });
    helper.select();
    try {
      if (!document.execCommand("copy")) window.prompt("Copy:", text);
    } catch (e) {
      window.prompt("Copy:", text);
    }
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).catch(function () { fallback(text); });
    } else {
      fallback(text);
    }
  }

  svg.addEventListener("click", function (event) {
    var text = anchorTitle(event.target) ||
               groupAnchorTitle(event.target) ||
               groupTitle(event.target);
    if (!text) return;
    event.preventDefault();
    copyText(text);
    var group = event.target;
    while (group && group !== svg) {
      if (group.tagName && group.tagName.toLowerCase() === "g") {
        var cls = group.getAttribute("class") || "";
        if (cls === "node" || cls === "edge") break;
      }
      group = group.parentNode;
    }
    if (group && group !== svg) {
      var old = group.style.opacity;
      group.style.opacity = "0.45";
      setTimeout(function () { group.style.opacity = old; }, 250);
    }
  });

  var style = document.createElementNS("http://www.w3.org/2000/svg", "style");
  style.textContent = "g.node, g.edge, a { cursor: copy; }";
  svg.appendChild(style);
})();
]]></script>
'''


def add_interactivity(svg_path):
    text = svg_path.read_text(encoding="utf-8")
    if "ttl2svg-copy" in text:
        return
    text = text.replace("</svg>", INTERACTIVE_SNIPPET + "</svg>")
    svg_path.write_text(text, encoding="utf-8")


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
        dot = build_uml_graph(ttl_path, args.engine, args.max_label_length,
                              args.interactive)
    else:
        dot = build_graph(ttl_path, args.engine, not args.no_literals,
                          args.max_label_length, args.interactive)
    rendered = dot.render(outfile=str(output_path))
    if args.interactive:
        add_interactivity(Path(rendered))
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
    if args.interactive and args.subjects_only:
        sys.exit("--interactive cannot be combined with --subjects-only")

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
                        help="UML-like box view: instances as boxes with their values, "
                             "edges only between instances")
    parser.add_argument("--interactive", action="store_true",
                        help="add full-value hover tooltips and click-to-copy")
    return parser.parse_args()


if __name__ == "__main__":
    main()
