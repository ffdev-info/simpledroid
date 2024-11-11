"""Create a simplified signature file for DROID using a PRONOM export.

Simplified DROID signature file example:

```
    <?xml version="1.0"?>
    <FFSignatureFile xmlns="http://www.nationalarchives.gov.uk/pronom/SignatureFile" Version="1" DateCreated="2024-09-18T12:46:55+00:00">
    <InternalSignatureCollection>
        <InternalSignature ID="3" Specificity="Specific">
            <ByteSequence Reference="BOFoffset" Sequence="04??[01:0C][01:1F]{28}([41:5A]|[61:7A]){10}(43|44|46|4C|4E)" Offset="0" />
        </InternalSignature>
    </InternalSignatureCollection>
    <FileFormatCollection>
        <FileFormat ID="1" Name="Development Signature" PUID="dev/1" Version="1.0" MIMEType="application/octet-stream">
        <InternalSignatureID>1</InternalSignatureID>
        <Extension>ext</Extension>
        </FileFormat>
    </FileFormatCollection>
    </FFSignatureFile>
```

"""

# pylint: disable=R0902,R0914

import argparse
import asyncio
import datetime
import logging
import os
import re
import sys
import time
import xml.dom.minidom
from dataclasses import dataclass
from datetime import timezone
from importlib.metadata import version
from typing import Final
from xml.dom.minidom import parse, parseString
from xml.sax.saxutils import escape

# Set up logging.
logging.basicConfig(
    format="%(asctime)-15s %(levelname)s :: %(filename)s:%(lineno)s:%(funcName)s() :: %(message)s",  # noqa: E501
    datefmt="%Y-%m-%d %H:%M:%S",
    level="INFO",
    handlers=[
        logging.StreamHandler(),
    ],
)

# Format logs using UTC time.
logging.Formatter.converter = time.gmtime


logger = logging.getLogger(__name__)


PRONOM_REGEX_ALLOWED: Final[str] = r"^[a-fA-F0-9\*\[\]??!&|(){}:-]+$"
UTC_TIME_FORMAT: Final[str] = "%Y-%m-%dT%H:%M:%SZ"


@dataclass
class ExternalSignature:
    id: str
    signature: str
    type: str


@dataclass
class ByteSequence:
    id: str
    pos: str
    min_off: str
    max_off: str
    endian: str
    value: str


@dataclass
class InternalSignature:
    id: str
    name: str
    byte_sequences: list[ByteSequence]


@dataclass
class Priority:
    type: str
    id: str


@dataclass
class Identifier:
    type: str
    value: str


@dataclass
class Format:
    id: str
    name: str
    version: str
    puid: str
    mime: str
    classification: str
    external_signatures: list[ExternalSignature]
    internal_signatures: list[InternalSignature]
    priorities: list[int]


def new_prettify(c):
    """Remove excess newlines from DOM output.

    via: https://stackoverflow.com/a/14493981
    """
    reparsed = parseString(c)
    return "\n".join(
        [
            line
            for line in reparsed.toprettyxml(indent=" " * 2).split("\n")
            if line.strip()
        ]
    )


def get_utc_timestamp_now():
    """Get a formatted UTC timestamp for 'now' that can be used when
    a timestamp is needed.
    """
    return datetime.datetime.now(timezone.utc).strftime(UTC_TIME_FORMAT)


def get_version():
    """Get script version."""
    try:
        return version("simpledroid")
    except Exception:  # pylint: disable=W0718
        return "0.0.0-dev"


def create_many_to_one_byte_sequence(internal_signatures: list[InternalSignature]):
    """Create a many to one byte sequence, i.e. a format with multiple
    Internal Signatures.
    """
    internal_signature = ""
    for internal in internal_signatures:
        id_ = internal.id
        bs = create_one_to_many_byte_sequence(internal.byte_sequences)
        internal_signature = f"""
{internal_signature}<InternalSignature ID=\"{id_}\" Specificity=\"Specific\">
    {bs}
</InternalSignature>
        """
    return internal_signature.strip()


def calculate_variable_off_bof(item: ByteSequence):
    """Given variable offsets, calculate the correct syntax."""
    seq = item.value
    if (
        item.min_off != ""
        and int(item.min_off) > 0
        and item.max_off != ""
        and int(item.max_off) > 0
    ):
        seq = f"{{{item.min_off}-{int(item.min_off)+int(item.max_off)}}}{seq}"
    elif item.max_off != "" and int(item.max_off) > 0:
        seq = f"{{0-{item.max_off}}}{seq}"
    elif item.min_off != "" and int(item.min_off) > 0:
        seq = f"{{{item.min_off}}}{seq}"
    return seq


def calculate_variable_off_eof(item: ByteSequence):
    """Given variable offsets, calculate the correct syntax."""
    seq = item.value
    if (
        item.min_off != ""
        and int(item.min_off) > 0
        and item.max_off != ""
        and int(item.max_off) > 0
    ):
        seq = f"{seq}{{{item.min_off}-{int(item.min_off)+int(item.max_off)}}}"
    elif item.max_off != "" and int(item.max_off) > 0:
        seq = f"{seq}{{0-{item.max_off}}}"
    elif item.min_off != "" and int(item.min_off) > 0:
        seq = f"{seq}{{{item.min_off}}}"
    return seq


def create_one_to_many_byte_sequence(byte_sequences: list[ByteSequence]):
    """Create a byte sequence object."""
    byte_sequence = ""
    for item in byte_sequences:
        seq = item.value
        if item.pos.startswith("EOF"):
            seq = calculate_variable_off_eof(item)
        elif item.pos.startswith("BOF"):
            seq = calculate_variable_off_bof(item)
        byte_sequence = f"""
{byte_sequence.strip()}
    <ByteSequence Reference=\"{item.pos}\" Sequence=\"{seq}\" MinOffset=\"{item.min_off}\" MaxOffset=\"{item.max_off}\"/>
        """
    return byte_sequence.strip()


def create_file_format_collection(fmt: list[Format]):
    """Create the FileFormatCollection object.

    ```
        <FileFormat ID="1" Name="Development Signature" PUID="dev/1" Version="1.0" MIMEType="application/octet-stream">
            <InternalSignatureID>1</InternalSignatureID>
            <Extension>ext</Extension>
        </FileFormat>

        <FileFormat ID="49" MIMEType="application/postscript"  FormatType="Text (Structured)"
            Name="Adobe Illustrator" PUID="x-fmt/20" Version="1.0 / 1.1">
            <InternalSignatureID>880</InternalSignatureID>
            <InternalSignatureID>881</InternalSignatureID>
            <Extension>ai</Extension>
            <HasPriorityOverFileFormatID>86</HasPriorityOverFileFormatID>
            <HasPriorityOverFileFormatID>331</HasPriorityOverFileFormatID>
            <HasPriorityOverFileFormatID>332</HasPriorityOverFileFormatID>
            <HasPriorityOverFileFormatID>771</HasPriorityOverFileFormatID>
            <HasPriorityOverFileFormatID>773</HasPriorityOverFileFormatID>
        </FileFormat>
    ```

    """

    EXT: Final[str] = "File extension"
    internal_sigs = [
        f"<InternalSignatureID>{sig.id}</InternalSignatureID>"
        for sig in fmt.internal_signatures
    ]
    external_sigs = [
        f"<Extension>{sig.signature}</Extension>"
        for sig in fmt.external_signatures
        if sig.type == EXT
    ]
    priorities = [
        f"<HasPriorityOverFileFormatID>{priority.id}</HasPriorityOverFileFormatID>"
        for priority in fmt.priorities
    ]

    ff = f"""
<FileFormat ID=\"{fmt.id}\" Name=\"{fmt.name}\" PUID=\"{fmt.puid}\" Version="{fmt.version}" MIMEType=\"{fmt.mime}\">
    {"".join(internal_sigs).strip()}
    {"".join(external_sigs).strip()}
    {"".join(priorities).strip()}
</FileFormat>
    """
    return ff.strip()


def pre_process_signature(item: str) -> str:
    """Pre-process a signature to remove some low-hanging compatibility
    issues, e.g. trim spaces, and make upper-case.
    """
    return item.strip().upper().replace(" ", "")


def _get_node_value(tag: str, node: xml.dom.minidom.Element) -> str:
    """Retrieve data based on its tag."""
    try:
        return node.getElementsByTagName(tag)[0].firstChild.nodeValue.strip()
    except IndexError:
        return None


def get_identifiers(identifiers: xml.dom.minicompat.NodeList):
    """Get identifiers for a format...

    ```
      <FileFormatIdentifier>
        <Identifier>font/ttf</Identifier>
        <IdentifierType>MIME</IdentifierType>
      </FileFormatIdentifier>
      <FileFormatIdentifier>
        <Identifier>x-fmt/453</Identifier>
        <IdentifierType>PUID</IdentifierType>
      </FileFormatIdentifier>
    ```

    """
    MIME: Final[str] = "MIME"
    PUID: Final[str] = "PUID"
    puid = ""
    mime = ""
    for identifier in identifiers:
        identifier_value = _get_node_value("Identifier", identifier)
        identifier_type = _get_node_value("IdentifierType", identifier)
        if identifier_type == MIME:
            mime = identifier_value
        if identifier_type == PUID:
            puid = identifier_value
    return puid, mime


def get_priorities(relationships: xml.dom.minicompat.NodeList):
    """Get priorities for a file format signature...

    ```
      <RelatedFormat>
        <RelationshipType>Has lower priority than</RelationshipType>
        <RelatedFormatID>613</RelatedFormatID>
        <RelatedFormatName>Acrobat PDF 1.0 - Portable Document Format</RelatedFormatName>
        <RelatedFormatVersion>1.0</RelatedFormatVersion>
      </RelatedFormat>
      <RelatedFormat>
    ```

    """
    priority_over: Final[str] = "Has priority over"
    priorities = []
    for related in relationships:
        rel_type = _get_node_value("RelationshipType", related)
        if rel_type != priority_over:
            continue
        rel_format_id = _get_node_value("RelatedFormatID", related)
        _ = _get_node_value("RelatedFormatName", related)
        _ = _get_node_value("RelatedFormatVersion", related)
        priorities.append(
            Priority(
                type=rel_type,
                id=rel_format_id,
            )
        )
    return priorities


def get_external(
    external_identifiers: xml.dom.minicompat.NodeList,
) -> list[ExternalSignature]:
    """Get external identifiers for a file format...

    ```
      <ExternalSignature>
        <ExternalSignatureID>861</ExternalSignatureID>
        <Signature>ttf</Signature>
        <SignatureType>File extension</SignatureType>
      </ExternalSignature>
    ```

    """
    external_signatures = []
    for external in external_identifiers:
        sig_id = _get_node_value("ExternalSignatureID", external)
        sig = _get_node_value("Signature", external)
        sig_type = _get_node_value("SignatureType", external)
        external_signatures.append(
            ExternalSignature(
                id=sig_id,
                signature=sig,
                type=sig_type,
            )
        )
    return external_signatures


def get_internal(internal_signatures: xml.dom.minicompat.NodeList):
    """Get byte-signatures for a file format...

    ```
      <InternalSignature>
        <SignatureID>242</SignatureID>
        <SignatureName>TrueType Font</SignatureName>
        <SignatureNote>OS/2, cmap (character to glyph mapping), glyf (glyph data), head(font header), hhea (horizontal header), hmtx (horizontal metrics), loca (index to location), maxp (maximum profile),name (naming table), post (PostScript information)</SignatureNote>
        <ByteSequence>
          <ByteSequenceID>315</ByteSequenceID>
          <PositionType>Absolute from BOF</PositionType>
          <Offset>12</Offset>
          <MaxOffset>128</MaxOffset>
          <IndirectOffsetLocation>
          </IndirectOffsetLocation>
          <IndirectOffsetLength>
          </IndirectOffsetLength>
          <Endianness>Little-endian</Endianness>
          <ByteSequenceValue>4F532F32{0-256}636D6170{0-256}676C7966{0-256}68656164{0-256}68686561{0-256}686D7478{0-256}6C6F6361{0-256}6D617870{0-256}6E616D65{0-256}706F7374</ByteSequenceValue>
        </ByteSequence>
      </InternalSignature>
    ```

    """
    internal_sigs = []
    for internal in internal_signatures:
        sig_id = _get_node_value("SignatureID", internal)
        sig_name = _get_node_value("SignatureName", internal)
        _ = _get_node_value("SignatureNote", internal)
        try:
            byte_sequences = internal.getElementsByTagName("ByteSequence")
            sequences = get_bytes(byte_sequences)
        except IndexError:
            continue
        internal_sigs.append(
            InternalSignature(
                id=sig_id,
                name=sig_name,
                byte_sequences=sequences,
            )
        )
    return internal_sigs


def get_bytes(byte_sequences: xml.dom.minicompat.NodeList):
    """Retrieve the byte sequences from the given node list.

    ```
        <ByteSequence>
          <ByteSequenceID>315</ByteSequenceID>
          <PositionType>Absolute from BOF</PositionType>
          <Offset>12</Offset>
          <MaxOffset>128</MaxOffset>
          <IndirectOffsetLocation>
          </IndirectOffsetLocation>
          <IndirectOffsetLength>
          </IndirectOffsetLength>
          <Endianness>Little-endian</Endianness>
          <ByteSequenceValue>4F532F32{0-256}636D6170{0-256}676C7966{0-256}68656164{0-256}68686561{0-256}686D7478{0-256}6C6F6361{0-256}6D617870{0-256}6E616D65{0-256}706F7374</ByteSequenceValue>
        </ByteSequence>
    ```

    """
    BOF: Final[str] = "BOFoffset"
    EOF: Final[str] = "EOFoffset"
    BOF_XML: Final[str] = "Absolute from BOF"
    EOF_XML: Final[str] = "Absolute from EOF"
    sequence_list = []
    for byte_sequence in byte_sequences:
        seq_id = _get_node_value("ByteSequenceID", byte_sequence)
        pos_type = _get_node_value("PositionType", byte_sequence)
        if pos_type == BOF_XML:
            pos_type = BOF
        elif pos_type == EOF_XML:
            pos_type = EOF
        else:
            pos_type = ""
        min_off = _get_node_value("Offset", byte_sequence)
        max_off = _get_node_value("MaxOffset", byte_sequence)
        _ = _get_node_value("IndirectOffsetLocation", byte_sequence)
        _ = _get_node_value("IndirectOffsetLength", byte_sequence)
        endian = _get_node_value("Endianness", byte_sequence)
        seq_value = _get_node_value("ByteSequenceValue", byte_sequence)
        valid_sig = re.fullmatch(PRONOM_REGEX_ALLOWED, seq_value)
        if not valid_sig:
            logger.error("signature '%s' is not valid", seq_value)
        if [
            val
            for val in ("??", "(", ")", "|", "{", "}", ":", "-", "[", "]", "*")
            if val in seq_value
        ]:
            pass
        elif len(seq_value) % 2 != 0:
            logger.error("rejecting sig data: '%s' based on length", seq_value)
            continue
        seq_value = pre_process_signature(seq_value)
        if "&" in seq_value:
            logger.error("signature might not function properly: '%s'", seq_value)
            seq_value = escape(seq_value)
        sequence_list.append(
            ByteSequence(
                id=seq_id,
                pos=pos_type,
                min_off=min_off,
                max_off=max_off,
                endian=endian,
                value=seq_value,
            )
        )
    return sequence_list


def process_formats_and_save(formats: list[Format], filename: str):
    """Process the collected formats and output a signature file.

    NB. Given our dataclasses here, we have the opportunity to rework
    this data into many new structures. We output XML because DROID
    expects XML.
    """
    isc = []
    ffc = []
    for fmt in formats:
        ffc.append(create_file_format_collection(fmt))
        if fmt.internal_signatures:
            isc.append(create_many_to_one_byte_sequence(fmt.internal_signatures))
    droid_template = f"""
<?xml version="1.0" encoding="UTF-8"?>
<FFSignatureFile xmlns='http://www.nationalarchives.gov.uk/pronom/SignatureFile' Version='1' DateCreated='{get_utc_timestamp_now()}'>
    <InternalSignatureCollection>
        {"".join(isc).strip()}
    </InternalSignatureCollection>
    <FileFormatCollection>
        {"".join(ffc).strip()}
    </FileFormatCollection>
</FFSignatureFile>
    """
    dom = xml.dom.minidom.parseString(droid_template.strip().replace("\n", ""))
    pretty_xml = dom.toprettyxml(indent=" ", encoding="utf-8")
    prettier_xml = new_prettify(pretty_xml)
    logger.info("outputting to: %s", filename)
    with open(filename, "w", encoding="utf=8") as output_file:
        output_file.write(prettier_xml)


async def process_pronom(report_list: list, filename: str):
    """Process a directory of PRONOM reports."""
    formats = []
    idx = 0
    for idx, report in enumerate(report_list):
        dom = None
        with open(report, "r", encoding="UTF-8") as pronom_file:
            dom = parse(pronom_file)
        format_id = _get_node_value("FormatID", dom)
        format_name = _get_node_value("FormatName", dom)
        format_version = _get_node_value("FormatVersion", dom)
        external_signature_elements = dom.getElementsByTagName("ExternalSignature")
        external_signatures = get_external(external_signature_elements)
        internal_signature_elements = dom.getElementsByTagName("InternalSignature")
        internal_signatures = get_internal(internal_signature_elements)
        identifier_elements = dom.getElementsByTagName("FileFormatIdentifier")
        puid, mime = get_identifiers(identifier_elements)
        if not external_signatures and not internal_signatures:
            continue
        format_types = _get_node_value("FormatTypes", dom)
        related_formats = dom.getElementsByTagName("RelatedFormat")
        priorities = get_priorities(related_formats)
        formats.append(
            Format(
                id=format_id,
                name=escape(format_name),
                version=escape(format_version),
                puid=puid,
                mime=mime,
                classification=format_types,
                external_signatures=external_signatures,
                internal_signatures=internal_signatures,
                priorities=priorities,
            )
        )
    logger.info("number of reports: %s", idx)
    logger.info("number of formats processed for the signature file: %s", len(formats))
    process_formats_and_save(formats, filename)


async def main():
    """Primary entry point for this script."""

    parser = argparse.ArgumentParser(
        prog="simpledroid",
        description="create a Simplified DROID signature file from a PRONOM export",
        epilog="for more information visit https://github.com/ross-spencer/simpledroid",
    )
    parser.add_argument(
        "--pronom",
        "-p",
        help="point to a set of droid reports, e.g. from builder",
        required=False,
        default=os.path.join(".", "pronom"),
    )
    parser.add_argument(
        "--output",
        "-o",
        help="filename to output to",
        default="DROID_SignatureFile_Simple.xml",
    )
    parser.add_argument(
        "--output-date",
        "-t",
        help="output a default file with the current timestamp",
        action="store_true",
    )
    args = parser.parse_args()
    filename = args.output
    if args.output_date:
        filename = f"DROID_SignatureFile_Simple_{get_utc_timestamp_now().replace(':', '-')}.xml"
    pronom_dir: Final[str] = args.pronom
    if not os.path.exists(pronom_dir):
        logger.error("pronom reports directory '%s' doesn't exist", pronom_dir)
        sys.exit(1)
    report_list = []
    for _, _, files in os.walk(pronom_dir):
        for file in files:
            report_list.append(os.path.join(pronom_dir, file))
    await process_pronom(report_list, filename)


if __name__ == "__main__":
    asyncio.run(main())
