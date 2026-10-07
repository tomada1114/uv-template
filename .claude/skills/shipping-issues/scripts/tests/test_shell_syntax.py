#!/usr/bin/env python3
"""Every bundled shell script parses under the system bash.

macOS ships bash 3.2 as /bin/bash, and `#!/usr/bin/env bash` picks it up on a Mac
without Homebrew's bash first on PATH. bash 3.2 misreads some constructs bash 5
accepts (a here-document inside `$(...)` whose body holds a backtick or quote), so a
script that passes on Linux can fail to parse on the machine that runs it.

The reverse holds for awk: Ubuntu's default awk is mawk, whose 1.3.4 release
(Ubuntu 24.04, the Claude Code cloud VM) panics on an interval expression such
as `{0,3}` in a regex literal, while macOS awk and GitHub's runners (gawk)
accept it. So no awk regex in a bundled script uses one.

Run: python3 -m unittest discover -s scripts/tests -p 'test_*.py'
     (from the shipping-issues skill directory)
"""
from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path


SCRIPTS = sorted((Path(__file__).resolve().parent.parent).glob("*.sh"))

# A /.../ regex literal holding a {n}, {n,} or {n,m} interval. bash's own
# `[[ =~ ]]` regexes carry no slashes, so they never match.
AWK_INTERVAL = re.compile(r"/[^/\n]*\{\d+(,\d*)?\}[^/\n]*/")


class ShellSyntaxTest(unittest.TestCase):
    def test_there_are_scripts_to_check(self):
        self.assertGreater(len(SCRIPTS), 0)

    def test_every_script_parses_under_the_system_bash(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                proc = subprocess.run(
                    ["/bin/bash", "-n", str(script)],
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_no_awk_regex_uses_an_interval_expression(self):
        for script in SCRIPTS:
            text = script.read_text(encoding="utf-8")
            for number, line in enumerate(text.splitlines(), start=1):
                with self.subTest(script=script.name, line=number):
                    self.assertIsNone(AWK_INTERVAL.search(line), line.strip())


if __name__ == "__main__":
    unittest.main()
