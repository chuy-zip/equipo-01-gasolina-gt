"""Genera DOCX y PDF con LibreOffice desde informe.md; requiere pandoc y pdfinfo."""

from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from zipfile import ZipFile


CARPETA = Path(__file__).resolve().parent
NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "style": "urn:oasis:names:tc:opendocument:xmlns:style:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "fo": "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
}
for prefijo, uri in NS.items():
    ET.register_namespace(prefijo, uri)


def q(nombre):
    prefijo, local = nombre.split(":")
    return f"{{{NS[prefijo]}}}{local}"


def propiedades(elemento, tipo, **atributos):
    hijo = elemento.find(q(tipo))
    if hijo is None:
        hijo = ET.SubElement(elemento, q(tipo))
    for nombre, valor in atributos.items():
        hijo.set(q(nombre), valor)


def dar_formato(origen, destino):
    with ZipFile(origen) as entrada, ZipFile(destino, "w") as salida:
        for item in entrada.infolist():
            datos = entrada.read(item.filename)
            if item.filename == "styles.xml":
                raiz = ET.fromstring(datos)
                for elemento in raiz.findall(".//style:page-layout-properties", NS):
                    for nombre, valor in {
                        "page-width": "21cm", "page-height": "29.7cm",
                        "margin-top": "1.8cm", "margin-bottom": "1.8cm",
                        "margin-left": "2cm", "margin-right": "2cm",
                    }.items():
                        elemento.set(q("fo:" + nombre), valor)
                for estilo in raiz.findall(".//style:style", NS):
                    nombre = estilo.get(q("style:name"), "")
                    if estilo.get(q("style:family")) == "paragraph":
                        propiedades(estilo, "style:text-properties", **{
                            "style:font-name": "Liberation Serif", "fo:font-family": "Liberation Serif",
                            "fo:font-size": "11pt", "fo:language": "es", "fo:country": "GT",
                        })
                        propiedades(estilo, "style:paragraph-properties", **{
                            "fo:margin-top": "0cm", "fo:margin-bottom": "0.17cm",
                            "fo:line-height": "110%", "fo:orphans": "2", "fo:widows": "2",
                        })
                    if nombre in ("Heading_20_1", "Heading_20_2"):
                        propiedades(estilo, "style:text-properties", **{
                            "fo:font-size": "17pt" if nombre.endswith("1") else "13pt",
                            "fo:font-weight": "bold", "fo:color": "#172c40",
                            "fo:font-style": "normal",
                        })
                        propiedades(estilo, "style:paragraph-properties", **{
                            "fo:margin-bottom": "0.25cm", "fo:keep-with-next": "always",
                            "fo:margin-left": "0cm", "fo:text-indent": "0cm", "fo:text-align": "left",
                        })
                    if nombre in ("Text_20_body", "Standard"):
                        propiedades(estilo, "style:paragraph-properties", **{"fo:text-align": "justify"})
                    if nombre == "Source_20_Text":
                        propiedades(estilo, "style:text-properties", **{"fo:font-size": "9pt"})
                estilos = raiz.find("office:styles", NS)
                nuevo = ET.SubElement(estilos, q("style:style"), {
                    q("style:name"): "SeccionPagina", q("style:family"): "paragraph",
                    q("style:parent-style-name"): "Heading_20_2",
                })
                propiedades(nuevo, "style:paragraph-properties", **{"fo:break-before": "page"})
                for nombre in ("InformeDatos", "InformeTabla"):
                    nuevo = ET.SubElement(estilos, q("style:style"), {
                        q("style:name"): nombre, q("style:family"): "paragraph",
                        q("style:parent-style-name"): "Text_20_body",
                    })
                    propiedades(nuevo, "style:paragraph-properties", **{"fo:text-align": "left"})
                datos = ET.tostring(raiz, encoding="utf-8", xml_declaration=True)
            elif item.filename == "content.xml":
                raiz = ET.fromstring(datos)
                for encabezado in raiz.findall(".//text:h", NS):
                    if re.match(r"[2-5]\. ", "".join(encabezado.itertext())):
                        encabezado.set(q("text:style-name"), "SeccionPagina")
                for parrafo in raiz.findall(".//table:table-cell/text:p", NS):
                    parrafo.set(q("text:style-name"), "InformeTabla")
                for parrafo in raiz.findall(".//office:text/text:p", NS):
                    if "".join(parrafo.itertext()).startswith("Monitoreo y predicción"):
                        parrafo.set(q("text:style-name"), "InformeDatos")
                datos = ET.tostring(raiz, encoding="utf-8", xml_declaration=True)
            salida.writestr(item, datos)


def main():
    for programa in ("pandoc", "libreoffice", "pdfinfo"):
        if shutil.which(programa) is None:
            raise SystemExit(f"Falta instalar {programa}")
    with tempfile.TemporaryDirectory(prefix="gas-informe-") as temporal:
        tmp = Path(temporal)
        subprocess.run(["pandoc", str(CARPETA / "informe.md"), "-o", str(tmp / "base.odt")], check=True)
        dar_formato(tmp / "base.odt", tmp / "informe.odt")
        oficina = ["libreoffice", f"-env:UserInstallation={(tmp / 'perfil').as_uri()}", "--headless"]
        subprocess.run(oficina + ["--convert-to", "docx:Office Open XML Text", "--outdir", str(tmp),
                                 str(tmp / "informe.odt")], check=True)
        subprocess.run(oficina + ["--convert-to", "pdf:writer_pdf_Export", "--outdir", str(tmp),
                                 str(tmp / "informe.docx")], check=True)
        info = subprocess.check_output(["pdfinfo", str(tmp / "informe.pdf")], text=True)
        paginas = int(re.search(r"Pages:\s+(\d+)", info).group(1))
        if paginas > 5:
            raise SystemExit(f"El informe ocupa {paginas} páginas; ajustar el Markdown antes de publicarlo.")
        for extension in ("docx", "pdf"):
            shutil.copyfile(tmp / f"informe.{extension}", CARPETA / f"informe.{extension}")
        shutil.copyfile(CARPETA / "informe.pdf", CARPETA.parent / "docs" / "informe.pdf")
        print(f"Generados informe/informe.docx, informe/informe.pdf y docs/informe.pdf ({paginas} páginas).")


if __name__ == "__main__":
    main()
