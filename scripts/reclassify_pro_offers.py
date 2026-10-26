"""Account repair entry point; preview by default, use --apply to write.

Pro-only redistribution was unsafe: an unspecified tier must never default to
20x. Use the full shared classifier to repair cross-brand assignments too.
"""
from reclassify_account_offers import main


if __name__ == "__main__":
    main()
