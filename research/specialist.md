To Add New Specialist:
1. Add prompt method to specialist.py:.

pythondef _ml_specialist_prompt(self, task):
    """MACHINE LEARNING SPECIALIST"""
    reqs = self._format_requirements(task.get('spec_requirements', []))
    return f"""You are an ML expert...
{reqs}
..."""

2. Register in prompts dict:
pythonprompts = {
    'graphics_specialist': self._graphics_prompt,
    'ml_specialist': self._ml_specialist_prompt,  # ADD THIS
    ...
}

3. Update SPEC.json:
json{
  "name": "model_training",
  "role": "ml_specialist",  # USE THE NEW ROLE
  "description": "...",
  "requirements": [...]
}