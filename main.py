"""Main entry point for KubeSight application."""

from kubesight.app import app


def main():
    """Run the Flask application."""
    import os
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=debug_mode)


if __name__ == "__main__":
    main()
