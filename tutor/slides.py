"""The lesson deck: one source of truth for the tutor's script and the UI."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Slide:
    number: int
    title: str
    bullets: tuple[str, ...]
    notes: str  # Speaker notes: what the tutor should cover on this slide.

    def to_dict(self) -> dict:
        return asdict(self)


DECK: tuple[Slide, ...] = (
    Slide(
        number=1,
        title="Welcome to Natural Disasters",
        bullets=(
            "What natural disasters are",
            "Why they happen",
            "How they affect people and nature",
            "How we stay safe",
        ),
        notes=(
            "Welcome the class and introduce today's topic: natural disasters. "
            "Say that you will cover what they are, why they happen, and how they affect "
            "people and the environment. Tell them questions are welcome at any time."
        ),
    ),
    Slide(
        number=2,
        title="What Are Natural Disasters?",
        bullets=(
            "Extreme events caused by nature",
            "They damage lives, homes and the environment",
            "Earthquakes, floods, hurricanes, volcanoes, droughts",
        ),
        notes=(
            "Explain that natural disasters are extreme natural events that cause major damage "
            "to life, property or the environment. Give examples: earthquakes, floods, "
            "hurricanes, volcanic eruptions and droughts. Stress that they come from natural "
            "processes of the Earth."
        ),
    ),
    Slide(
        number=3,
        title="Why Do They Happen?",
        bullets=(
            "Moving tectonic plates",
            "Extreme weather",
            "Volcanic activity",
            "Some are sudden, some build up slowly",
        ),
        notes=(
            "Describe the main causes: movement of tectonic plates, extreme weather patterns, "
            "volcanic activity and climate-related changes. Mention that some disasters strike "
            "suddenly while others develop slowly over time."
        ),
    ),
    Slide(
        number=4,
        title="Major Types",
        bullets=(
            "Earthquakes and landslides",
            "Floods and cyclones",
            "Wildfires",
            "Volcanic eruptions",
        ),
        notes=(
            "Introduce the most common types: earthquakes, floods, cyclones, wildfires, "
            "landslides and volcanic eruptions. Explain that each has different causes and "
            "impacts depending on geography and climate."
        ),
    ),
    Slide(
        number=5,
        title="Impact on People",
        bullets=(
            "Injuries and loss of life",
            "Homes destroyed, families displaced",
            "Schools and hospitals disrupted",
        ),
        notes=(
            "Explain how disasters affect communities: injuries and loss of life, destroyed "
            "homes and families having to move. Mention disruption to healthcare, schools and "
            "daily life. Keep the tone gentle and age-appropriate."
        ),
    ),
    Slide(
        number=6,
        title="Effects on the Environment",
        bullets=(
            "Forests lost to wildfires",
            "Flooded habitats and soil erosion",
            "Polluted water",
            "Landscapes reshaped over time",
        ),
        notes=(
            "Describe effects on ecosystems: forests lost to wildfires, flooded habitats, soil "
            "erosion and polluted water sources. Mention that disasters also reshape landscapes "
            "and ecosystems over time."
        ),
    ),
    Slide(
        number=7,
        title="Being Prepared",
        bullets=(
            "Early warning systems",
            "Evacuation plans",
            "Emergency kits",
            "Learning and practising together",
        ),
        notes=(
            "Explain how preparation reduces damage and saves lives: early warning systems, "
            "evacuation plans, emergency kits and community awareness. Highlight that learning "
            "and planning ahead make people safer."
        ),
    ),
    Slide(
        number=8,
        title="Wrapping Up",
        bullets=(
            "Disasters are powerful natural events",
            "Understanding them helps us prepare",
            "Communities are stronger together",
        ),
        notes=(
            "Summarise the lesson: natural disasters are powerful natural events with serious "
            "effects on people and the environment. Stress preparedness, science and working "
            "together as a community."
        ),
    ),
)
