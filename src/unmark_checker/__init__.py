"""unmark-checker: plant a text watermark with your own key, then measure what a
watermark-removal tool did to it.

The package is deliberately small and its parts are usable on their own:

    thresholds  frozen detection thresholds and the three outcomes
    schemes     scheme presets; keys are derived from your secret, never stored
    watermark   model loading and generation with or without the mark
    detector    the key-aware mean g-value detector
    corpus      control texts that carry no mark
    identify    is the returned text still the sample?
    kpi         the metric set: meaning, facts, verbatim, changed share, length
    matrix      one summary table out of a folder of service files
"""

__version__ = "0.1.0"
