"""Stage inits — re-export all stage modules for clean imports."""
from engine.stages import (
    s1_understand,
    s2_static,
    s3_depgraph,
    s4_knowledge,
    s5_testgen,
    s6_executor,
    s7_diagnosis,
    s8_report,
)
