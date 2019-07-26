import base64
import os

from .definitions import get_definitions
from .helpers import (definition_summary, make_ranges, wrap_contents)


class FileExporter:
    def __init__(self, emitter, project_id):
        self.emitter = emitter
        self.project_id = project_id
        self.definition_metas = {}
        self.reference_range_ids = []

    def export(self, filename):
        print('File: {}'.format(filename))

        with open(filename) as f:
            source = f.read()

        self.source_lines = source.split('\n')
        self.definitions = get_definitions(source, filename)

        self.document_id = self.emitter.emit_document(
            'file://{}'.format(os.path.abspath(filename)),
            'py',
            base64.b64encode(source.encode('utf-8')).decode(),
        )

        self._export_defs()
        self._export_uses()

        meta_set = self.definition_metas.values()
        definition_range_ids = map(lambda m: m.range_id, meta_set)
        all_range_ids = list(definition_range_ids) + self.reference_range_ids

        self.emitter.emit_contains(self.project_id, [self.document_id])
        self.emitter.emit_contains(self.document_id, all_range_ids)

    def _export_defs(self):
        for definition in self.definitions:
            if not definition.is_definition():
                continue

            self._export_def_pre_use(definition)

    def _export_uses(self):
        for definition, meta in self.definition_metas.items():
            self._export_assignments(definition, meta)

    def _export_def_pre_use(self, definition):
        contents = {
            'language': 'py',
            'value': definition_summary(self.source_lines, definition),
        }

        result_set_id = self.emitter.emit_resultset()
        range_id = self.emitter.emit_range(*make_ranges(definition))
        hover_id = self.emitter.emit_hoverresult(wrap_contents(contents))

        self.emitter.emit_next(range_id, result_set_id)
        self.emitter.emit_hover(result_set_id, hover_id)

        self.definition_metas[definition] = DefinitionMeta(
            range_id,
            result_set_id,
            contents,
        )

    def _export_def_post_use(self, definition, meta, reference_range_ids):
        result_id = self.emitter.emit_referenceresult()
        self.emitter.emit_references(meta.result_set_id, result_id)
        self.emitter.emit_item(
            result_id,
            [meta.range_id],
            self.document_id,
            'definitions',
        )

        if len(reference_range_ids) > 0:
            self.emitter.emit_item(
                result_id,
                reference_range_ids,
                self.document_id,
                'references',
            )

    def _export_assignments(self, definition, meta):
        reference_range_ids = []
        for assignment in definition.goto_assignments():
            if assignment.line is None:
                continue

            reference_range_ids.append(self._export_use(
                definition,
                assignment,
                meta,
            ))

        self.reference_range_ids.extend(reference_range_ids)
        self._export_def_post_use(definition, meta, reference_range_ids)

    def _export_use(self, definition, assignment, meta):
        range_id = self.emitter.emit_range(*make_ranges(definition))
        result_id = self.emitter.emit_definitionresult()
        hover_id = self.emitter.emit_hoverresult(wrap_contents(meta.contents))

        self.emitter.emit_next(range_id, meta.result_set_id)
        self.emitter.emit_definition(meta.result_set_id, result_id)
        self.emitter.emit_item(result_id, [meta.range_id], self.document_id)
        self.emitter.emit_hover(meta.result_set_id, hover_id)

        return range_id


class DefinitionMeta:
    def __init__(self, range_id, result_set_id, contents):
        self.range_id = range_id
        self.result_set_id = result_set_id
        self.contents = contents
