import re
import sys

import compare
import run


def main(argv=None):
    base, body_file = argv if argv is not None else sys.argv[1:]
    cases = compare.covering(run.CASES, compare.changed_files(base, run.ROOT))
    if not cases:
        print("No eval case covers a changed skill, so no eval stamp is needed.")
        return 0
    expected = compare.stamp(cases, run.ROOT)
    found = re.findall(re.escape(compare.STAMP) + r"\s*([0-9a-f]{16})", open(body_file).read())
    if expected in found:
        print(f"Eval stamp {expected} matches the {len(cases)} cases covering the changed skills.")
        return 0
    skills = ", ".join(sorted({name for c in cases for name in compare.plugin_eval.skills(c)}))
    print(f"::error::This PR changes skills that {len(cases)} eval cases cover ({skills}), but the PR body has "
          f"{'a stale' if found else 'no'} eval stamp. Run `python3 -B evals/compare.py {base} --model "
          f"claude-opus-5-5` on the PR head, then paste the eval-stamp line it prints into the PR body.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
