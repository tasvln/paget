"""
Auto-generated entry point for project 'calculator'.
Generated once all 2 component(s) passed validation.

Uses importlib instead of plain 'import' because component ids
(and therefore filenames) contain hyphens, e.g. 'calculator-adder.py' —
'import calculator-adder' is not valid Python syntax.
"""

import importlib.util
import os

_here = os.path.dirname(os.path.abspath(__file__))
_modules = {}

def _load(component_id):
    path = os.path.join(_here, f'{component_id}.py')
    spec = importlib.util.spec_from_file_location(component_id, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

_modules['calculator-adder'] = _load('calculator-adder')
_modules['calculator-multiplier'] = _load('calculator-multiplier')

if __name__ == '__main__':
    print('calculator: all components loaded successfully')
    print('  - calculator-adder:', _modules['calculator-adder'].__file__)
    print('  - calculator-multiplier:', _modules['calculator-multiplier'].__file__)
