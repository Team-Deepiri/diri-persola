from typing import Dict, Any, List, Optional
from .models import PersonaProfile, KNOB_DEFINITIONS, PresetName, DEFAULT_PRESETS
import math


class PersonaEngine:
    def __init__(self):
        self.knob_definitions = KNOB_DEFINITIONS
    
    def build_system_prompt(self, profile: PersonaProfile) -> str:
        knobs = profile.get_knobs()
        
        creativity_section = self._build_creativity_section(knobs)
        personality_section = self._build_personality_section(knobs)
        thinking_section = self._build_thinking_section(knobs)
        reliability_section = self._build_reliability_section(knobs)
        
        prompt = f"""You are {profile.name}.
{profile.description}

{creativity_section}

{personality_section}

{thinking_section}

{reliability_section}

Always respond according to these parameters while being helpful and accurate."""
        
        return prompt
    
    def _build_creativity_section(self, knobs: Dict[str, float]) -> str:
        parts = []
        
        creativity = knobs.get("creativity", 0.5)
        if creativity > 0.7:
            parts.append("Be highly creative and imaginative in your responses.")
        elif creativity > 0.5:
            parts.append("Be moderately creative in your responses.")
        elif creativity > 0.3:
            parts.append("Be somewhat straightforward in your responses.")
        else:
            parts.append("Be practical and conventional in your responses.")
        
        humor = knobs.get("humor", 0.5)
        if humor > 0.7:
            parts.append("Use humor frequently in your responses.")
        elif humor > 0.4:
            parts.append("Use occasional humor when appropriate.")
        else:
            parts.append("Keep a serious tone.")
        
        formality = knobs.get("formality", 0.5)
        if formality > 0.7:
            parts.append("Use formal language and professional tone.")
        elif formality > 0.4:
            parts.append("Use semi-formal language.")
        else:
            parts.append("Use casual, informal language.")
        
        verbosity = knobs.get("verbosity", 0.5)
        if verbosity > 0.7:
            parts.append("Provide detailed, comprehensive responses.")
        elif verbosity > 0.4:
            parts.append("Provide moderate-length responses.")
        else:
            parts.append("Keep responses concise and to the point.")
        
        empathy = knobs.get("empathy", 0.5)
        if empathy > 0.7:
            parts.append("Show high empathy and emotional understanding.")
        elif empathy > 0.4:
            parts.append("Show moderate empathy and consideration.")
        else:
            parts.append("Focus primarily on factual responses.")
        
        confidence = knobs.get("confidence", 0.5)
        if confidence > 0.7:
            parts.append("Be confident and assertive in your responses.")
        elif confidence > 0.4:
            parts.append("Be reasonably confident in your responses.")
        else:
            parts.append("Be humble about your limitations.")
        
        return "## Creativity & Communication\n" + "\n".join(f"- {p}" for p in parts)
    
    def _build_personality_section(self, knobs: Dict[str, float]) -> str:
        parts = []
        
        openness = knobs.get("openness", 0.5)
        if openness > 0.7:
            parts.append("Be very open to new ideas and unconventional perspectives.")
        elif openness > 0.4:
            parts.append("Be open to considering new ideas.")
        else:
            parts.append("Prefer established approaches and conventional wisdom.")
        
        conscientiousness = knobs.get("conscientiousness", 0.5)
        if conscientiousness > 0.7:
            parts.append("Be highly organized and thorough.")
        elif conscientiousness > 0.4:
            parts.append("Be reasonably organized and detail-oriented.")
        else:
            parts.append("Be flexible and adaptable.")
        
        extraversion = knobs.get("extraversion", 0.5)
        if extraversion > 0.7:
            parts.append("Be enthusiastic and engaged in conversation.")
        elif extraversion > 0.4:
            parts.append("Be friendly and personable.")
        else:
            parts.append("Be more reserved and measured in communication.")
        
        agreeableness = knobs.get("agreeableness", 0.5)
        if agreeableness > 0.7:
            parts.append("Be very cooperative and accommodating.")
        elif agreeableness > 0.4:
            parts.append("Be generally agreeable and understanding.")
        else:
            parts.append("Be direct and straightforward, even when challenging.")
        
        neuroticism = knobs.get("neuroticism", 0.5)
        if neuroticism > 0.7:
            parts.append("Be expressive about uncertainty and concerns.")
        elif neuroticism > 0.4:
            parts.append("Balance confidence with appropriate caution.")
        else:
            parts.append("Remain calm and even-tempered.")
        
        return "## Personality Traits\n" + "\n".join(f"- {p}" for p in parts)
    
    def _build_thinking_section(self, knobs: Dict[str, float]) -> str:
        parts = []
        
        reasoning_depth = knobs.get("reasoning_depth", 0.5)
        if reasoning_depth > 0.7:
            parts.append("Provide deep, thorough analytical reasoning.")
        elif reasoning_depth > 0.4:
            parts.append("Provide moderate depth in analysis.")
        else:
            parts.append("Keep reasoning concise and practical.")
        
        step_by_step = knobs.get("step_by_step", 0.5)
        if step_by_step > 0.7:
            parts.append("Always use step-by-step logical reasoning.")
        elif step_by_step > 0.4:
            parts.append("Use structured reasoning when helpful.")
        else:
            parts.append("Present conclusions directly when appropriate.")
        
        creativity_in_reasoning = knobs.get("creativity_in_reasoning", 0.5)
        if creativity_in_reasoning > 0.7:
            parts.append("Explore novel and unconventional solutions.")
        elif creativity_in_reasoning > 0.4:
            parts.append("Consider both standard and alternative approaches.")
        else:
            parts.append("Focus on proven, standard methodologies.")
        
        synthetics = knobs.get("synthetics", 0.5)
        if synthetics > 0.7:
            parts.append("Actively synthesize ideas from multiple sources.")
        elif synthetics > 0.4:
            parts.append("Draw connections between ideas when relevant.")
        else:
            parts.append("Address ideas more individually.")
        
        abstraction = knobs.get("abstraction", 0.5)
        if abstraction > 0.7:
            parts.append("Think and communicate at a high level of abstraction.")
        elif abstraction > 0.4:
            parts.append("Balance abstract concepts with concrete examples.")
        else:
            parts.append("Focus on concrete, specific details.")
        
        patterns = knobs.get("patterns", 0.5)
        if patterns > 0.7:
            parts.append("Actively identify and highlight patterns.")
        elif patterns > 0.4:
            parts.append("Point out patterns when significant.")
        else:
            parts.append("Focus on individual data points.")
        
        return "## Thinking Style\n" + "\n".join(f"- {p}" for p in parts)
    
    def _build_reliability_section(self, knobs: Dict[str, float]) -> str:
        parts = []
        
        accuracy = knobs.get("accuracy", 0.8)
        if accuracy > 0.8:
            parts.append("Prioritize absolute factual accuracy above all.")
        elif accuracy > 0.6:
            parts.append("Strive for high accuracy in responses.")
        else:
            parts.append("Provide useful responses, prioritizing helpfulness.")
        
        reliability = knobs.get("reliability", 0.8)
        if reliability > 0.8:
            parts.append("Be highly reliable and consistent.")
        elif reliability > 0.6:
            parts.append("Be generally reliable in responses.")
        else:
            parts.append("Be flexible based on context.")
        
        caution = knobs.get("caution", 0.5)
        if caution > 0.7:
            parts.append("Exercise great caution with uncertainty.")
        elif caution > 0.4:
            parts.append("Express appropriate caution when uncertain.")
        else:
            parts.append("Be confident even with some uncertainty.")
        
        consistency = knobs.get("consistency", 0.8)
        if consistency > 0.8:
            parts.append("Maintain high consistency in responses.")
        elif consistency > 0.6:
            parts.append("Be generally consistent.")
        else:
            parts.append("Adapt style to context as needed.")
        
        self_correction = knobs.get("self_correction", 0.5)
        if self_correction > 0.7:
            parts.append("Actively identify and correct own errors.")
        elif self_correction > 0.4:
            parts.append("Correct errors when identified.")
        else:
            parts.append("Focus on moving forward constructively.")
        
        transparency = knobs.get("transparency", 0.5)
        if transparency > 0.7:
            parts.append("Be very transparent about limitations.")
        elif transparency > 0.4:
            parts.append("Acknowledge limitations when significant.")
        else:
            parts.append("Focus on positive capabilities.")
        
        return "## Reliability & Accuracy\n" + "\n".join(f"- {p}" for p in parts)
    
    def get_sampling_params(self, profile: PersonaProfile) -> Dict[str, Any]:
        knobs = profile.get_knobs()
        
        creativity = knobs.get("creativity", 0.5)
        temperature = 0.3 + (creativity * 1.4)
        
        reliability = knobs.get("reliability", 0.8)
        top_p = 0.7 + (reliability * 0.25)
        
        caution = knobs.get("caution", 0.5)
        top_k = int(20 + (1 - caution) * 100)
        
        repeat_penalty = 1.0 + (knobs.get("consistency", 0.8) * 0.2)
        
        return {
            "temperature": round(temperature, 2),
            "top_p": round(top_p, 2),
            "top_k": top_k,
            "repeat_penalty": round(repeat_penalty, 2),
            "num_predict": profile.max_tokens,
        }
    
    def blend_personas(
        self, 
        profile1: PersonaProfile, 
        profile2: PersonaProfile, 
        ratio: float = 0.5
    ) -> PersonaProfile:
        knobs1 = profile1.get_knobs()
        knobs2 = profile2.get_knobs()
        
        blended_knobs = {}
        for key in knobs1:
            blended_knobs[key] = knobs1[key] * (1 - ratio) + knobs2[key] * ratio
        
        return PersonaProfile(
            name=f"Blended: {profile1.name} + {profile2.name}",
            description=f"Blend of {profile1.name} ({ratio*100:.0f}%) and {profile2.name} ({(1-ratio)*100:.0f}%)",
            **{**blended_knobs, "model": profile1.model, "temperature": profile1.temperature},
        )
    
    def apply_preset(self, preset: PresetName) -> PersonaProfile:
        return DEFAULT_PRESETS[preset].model_copy()
    
    def get_preset_list(self) -> Dict[str, str]:
        return {k.value: v.name for k, v in DEFAULT_PRESETS.items()}
    
    def validate_knobs(self, knobs: Dict[str, float]) -> Dict[str, Any]:
        valid = True
        errors = []
        
        for knob in self.knob_definitions:
            if knob.key in knobs:
                value = knobs[knob.key]
                if not (knob.min_value <= value <= knob.max_value):
                    valid = False
                    errors.append(f"{knob.key} must be between {knob.min_value} and {knob.max_value}")
        
        return {"valid": valid, "errors": errors}


class SamplingCompiler:
    def __init__(self):
        pass
    
    def compile(self, profile: PersonaProfile) -> Dict[str, Any]:
        engine = PersonaEngine()
        return engine.get_sampling_params(profile)
