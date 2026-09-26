#!/usr/bin/env python3
# -*- coding: UTF-8 -*-


from __future__ import absolute_import

from .plantuml import PlantUMLProcessor
from .sublime import SublimeViewer
from .quicklook import QuickLookViewer
from .preview import PreviewViewer
from .eog import EyeOfGnomeViewer
from .freedesktop_default import FreedesktopDefaultViewer
from .windows import WindowsDefaultViewer

from debug_tools import getLogger
from threading import Thread
from sublime import error_message, load_settings

import sys

log = getLogger(__name__)
INITIALIZED = False

AVAILABLE_PROCESSORS = [PlantUMLProcessor]
AVAILABLE_VIEWERS = [
    SublimeViewer,
    QuickLookViewer,
    EyeOfGnomeViewer,
    PreviewViewer,
    FreedesktopDefaultViewer,
    WindowsDefaultViewer,
]

ACTIVE_UML_PROCESSORS = []
ACTIVE_VIEWER = None


def setup():
    global INITIALIZED
    sublime_settings = load_settings("PlantUmlDiagrams.sublime-settings")

    log._debug_level = 1 + sublime_settings.get('check_on_startup', 0)
    _load_viewer(sublime_settings)
    _load_preprocessor(sublime_settings)

    INITIALIZED = True
    log(4, "Processors: %s", ACTIVE_UML_PROCESSORS)
    log(4, "Viewer: %s", ACTIVE_VIEWER)


def _load_preprocessor(sublime_settings):
    global ACTIVE_UML_PROCESSORS
    ACTIVE_UML_PROCESSORS = []

    def load_preprocessor():

        try:
            log(4, "Loading plantuml_processor class: %s", plantuml_processor)
            proc = plantuml_processor()
            proc.CHARSET = sublime_settings.get('charset', None)
            proc.CHECK_ON_STARTUP = sublime_settings.get('check_on_startup', 1)
            proc.NEW_FILE = sublime_settings.get('new_file', True)
            proc.OUTPUT_FORMAT = sublime_settings.get('output_format', 'png')
            proc.load()

            ACTIVE_UML_PROCESSORS.append(proc)
            log(4, "Loaded plantuml_processor: %s", proc)
            return True

        except Exception as error:
            log(1, "Unable to load plantuml_processor: %s, %s", plantuml_processor, error)

        return False

    for plantuml_processor in AVAILABLE_PROCESSORS:

        if load_preprocessor():
            break

    if not ACTIVE_UML_PROCESSORS:
        log(1, 'PlantUMLDiagrams: ERROR, no working processors found!' )


def _load_viewer(sublime_settings):
    global ACTIVE_VIEWER
    ACTIVE_VIEWER = None

    # log(1, "PlantUmlDiagrams Viewer Setting: %s", sublime_settings.get("viewer"))

    def load_viewer(message):

        try:
            # log(1, "Loading viewer class: %s", viewer)
            vwr = viewer()
            vwr.load()

            global ACTIVE_VIEWER
            ACTIVE_VIEWER = vwr

            if not message:
                log(1, "Loaded viewer: %s", vwr)

            return True

        except Exception as error:

            if message:
                log(1, "Unable to load configured viewer %s, falling back to autodetection... %s", vwr, error)

        return False

    for viewer in AVAILABLE_VIEWERS:
        viewer_setting = sublime_settings.get("viewer")

        if not viewer_setting:
            print("PlantUMLDiagrams: No viewer setting found. Skipping viewer load.")
            continue

        if not viewer:
            print("PlantUMLDiagrams: None viewer found. Skipping viewer load.")
            continue

        if viewer.__name__.find(viewer_setting) != -1:
            load_viewer(True)
            break

    if ACTIVE_VIEWER is None:

        for viewer in AVAILABLE_VIEWERS:

            if load_viewer(False):
                break

    if ACTIVE_VIEWER is None:
        raise Exception('No working viewers found!')


def process(view, continuous_processor=None):
    diagrams = []

    if continuous_processor:
        run_async=False

    else:
        run_async=True

    for plantuml_processor in ACTIVE_UML_PROCESSORS:
        log(4, "plantuml_processor %s", plantuml_processor)
        text_blocks = []

        for text_block in plantuml_processor.extract_blocks(view):
            log(4, "text_block %s", text_block)
            add = False

            for selection in view.sel():

                if selection.intersects(text_block):
                    add = True
                    break

            else:  # if there are no selections, add all text_blocks
                add = True

            if add:
                text_blocks.append(view.substr(text_block))

        if text_blocks:
            diagrams.append((plantuml_processor, text_blocks, ))

    if diagrams:
        sourceFile = view.file_name()

        if run_async:
            t = Thread(target=render_and_view, args=(sourceFile, diagrams, continuous_processor))
            t.daemon = True
            t.start()

        else:
            render_and_view(sourceFile, diagrams, continuous_processor)

        return True

    else:
        return False


def render_and_view(sourceFile, diagrams, continuous_processor):
    # log(1, "Rendering %s", diagrams)
    sequence = [0]
    diagram_files = []

    for plantuml_processor, text_blocks in diagrams:
        diagram_files.extend(plantuml_processor.process(sourceFile, text_blocks, sequence, continuous_processor))
        sequence[0] += 1

    if diagram_files:
        names = [d.name for d in diagram_files if d]

        if continuous_processor:

            if continuous_processor.open_image:
                log(1, "continuous_processor: %s viewing %s", ACTIVE_VIEWER, names)
                ACTIVE_VIEWER.view(diagram_files)
                continuous_processor.open_image = False

        else:
            log(1, "%s viewing %s", ACTIVE_VIEWER, names)
            ACTIVE_VIEWER.view(diagram_files)

    else:
        error_message("No diagrams generated...")
