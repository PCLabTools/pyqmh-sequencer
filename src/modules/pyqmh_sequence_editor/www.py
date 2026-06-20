"""
file: pyqmh_sequence_editor/www.py
description: pyqmh Sequence Editor for creating, editing and managing pyqmh sequence files
author: Larry
"""

import json
import logging
import os
import threading

from flask import Flask, abort, redirect, render_template, request, send_from_directory, url_for
from jinja2 import Environment, FileSystemLoader, select_autoescape


class ModuleWebGui:
	"""Owns Flask app setup, routes, and server startup for a module app."""

	def __init__(self, logger: logging.Logger, module_folder_name: str):
		self.logger = logger
		self.module_folder_name = module_folder_name
		self.src_dir = os.path.dirname(__file__)
		self._routes_config = self._load_routes_config()
		self.flask_app = self._create_flask_app()

	def start(self) -> threading.Thread:
		"""Start the module Flask server in a background daemon thread."""
		flask_thread = threading.Thread(
			target=lambda: self.flask_app.run(
				host="0.0.0.0",
				port=5000,
				debug=False,
				use_reloader=False,
			),
			daemon=True,
			name="flask-server",
		)
		flask_thread.start()
		self.logger.info("Flask server started on http://localhost:5000")
		return flask_thread

	def _load_routes_config(self) -> dict:
		routes_file = os.path.join(self.src_dir, "routes.json")
		if not os.path.isfile(routes_file):
			return {}

		try:
			with open(routes_file, "r", encoding="utf-8") as handle:
				data = json.load(handle)
			if isinstance(data, dict):
				return data
			self.logger.warning("Ignoring routes.json: expected a JSON object at the top level.")
		except (OSError, json.JSONDecodeError) as exc:
			self.logger.warning("Failed to read routes.json: %s", exc)
		return {}

	def _discover_module_web_apps(self) -> list:
		modules_dir = os.path.join(self.src_dir, "modules")
		if not os.path.isdir(modules_dir):
			self.logger.debug("Modules directory not found. Navigation will show no modules.")
			return []

		result = []
		for name in sorted(os.listdir(modules_dir)):
			if name.startswith("_"):
				continue
			www_path = os.path.join(modules_dir, name, "www")
			if os.path.isdir(www_path):
				result.append(name)
		return result

	def _path_is_active(self, current_path: str, target_path: str) -> bool:
		if target_path == "/":
			return current_path == "/"
		return current_path == target_path or current_path.startswith(target_path + "/")

	def _resolve_module_nav_path(self, path: str, module_base_path: str) -> str:
		if not isinstance(path, str) or not path:
			return "#"

		if not module_base_path:
			return path

		if path.startswith("http://") or path.startswith("https://") or path.startswith("#"):
			return path

		if path == module_base_path or path.startswith(module_base_path + "/"):
			return path

		if path == "/":
			return module_base_path

		if path.startswith("/"):
			return f"{module_base_path}{path}"

		return path

	def _build_nav_items_from_routes(self, module_base_path: str, current_path: str) -> list:
		nav_items = []
		for label, value in self._routes_config.items():
			if str(label).lower() == "modules":
				if not isinstance(value, dict):
					continue

				dropdown_items = []
				for module_label, module_path in value.items():
					if not isinstance(module_label, str) or not isinstance(module_path, str):
						continue
					resolved_path = self._resolve_module_nav_path(module_path, module_base_path)
					dropdown_items.append(
						{
							"label": module_label,
							"path": resolved_path,
							"active": self._path_is_active(current_path, resolved_path),
						}
					)

				if dropdown_items:
					nav_items.append(
						{
							"type": "dropdown",
							"label": "Modules",
							"items": dropdown_items,
							"active": any(item["active"] for item in dropdown_items),
						}
					)
				continue

			if not isinstance(label, str) or not isinstance(value, str):
				continue

			resolved_path = self._resolve_module_nav_path(value, module_base_path)
			nav_items.append(
				{
					"type": "link",
					"label": label,
					"path": resolved_path,
					"active": self._path_is_active(current_path, resolved_path),
				}
			)

		return nav_items

	def _build_default_nav_items(self, modules: list, module_base_path: str, show_home_about: bool, current_path: str) -> list:
		nav_items = []

		if show_home_about:
			home_path = module_base_path or "/"
			nav_items.append(
				{
					"type": "link",
					"label": "Home",
					"path": home_path,
					"active": self._path_is_active(current_path, home_path),
				}
			)

		if modules:
			dropdown_items = []
			for module in modules:
				module_path = f"{module_base_path}/module/{module}" if module_base_path else f"/module/{module}"
				dropdown_items.append(
					{
						"label": module.replace("_", " ").title(),
						"path": module_path,
						"active": self._path_is_active(current_path, module_path),
					}
				)

			nav_items.append(
				{
					"type": "dropdown",
					"label": "Modules",
					"items": dropdown_items,
					"active": any(item["active"] for item in dropdown_items),
				}
			)

		if show_home_about:
			about_path = f"{module_base_path}/about" if module_base_path else "/about"
			nav_items.append(
				{
					"type": "link",
					"label": "About",
					"path": about_path,
					"active": self._path_is_active(current_path, about_path),
				}
			)

		return nav_items

	def _template_context(self, modules: list, embedded_mode: bool, current_path: str) -> dict:
		base_path = "" if not embedded_mode else f"/module/{self.module_folder_name}/app"
		show_home_about = not embedded_mode
		if self._routes_config:
			nav_items = self._build_nav_items_from_routes(base_path, current_path)
		else:
			nav_items = self._build_default_nav_items(modules, base_path, show_home_about, current_path)

		return {
			"modules": modules,
			"show_nav": bool(nav_items),
			"show_home_about": show_home_about,
			"embedded_mode": embedded_mode,
			"module_base_path": base_path,
			"nav_items": nav_items,
		}

	def _create_flask_app(self) -> Flask:
		flask_app = Flask(
			__name__,
			template_folder=os.path.join(self.src_dir, "www", "templates"),
			static_folder=os.path.join(self.src_dir, "www", "static"),
		)

		module_names = self._discover_module_web_apps()

		@flask_app.route("/")
		def index():
			return render_template(
				"index.html",
				**self._template_context(module_names, embedded_mode=False, current_path=request.path),
			)

		@flask_app.route("/about")
		def about():
			return render_template(
				"about.html",
				**self._template_context(module_names, embedded_mode=False, current_path=request.path),
			)

		@flask_app.route("/module/<name>")
		def module_page(name):
			if name in module_names:
				return redirect(url_for("submodule_app", name=name))
			return redirect(url_for("index"))

		@flask_app.route("/module/<name>/app/")
		@flask_app.route("/module/<name>/app/index")
		def submodule_app(name):
			if name not in module_names:
				return redirect(url_for("index"))

			templates_dir = os.path.join(self.src_dir, "modules", name, "www", "templates")
			index_file = os.path.join(templates_dir, "index.html")
			if not os.path.isfile(index_file):
				abort(404)

			submodule_env = Environment(
				loader=FileSystemLoader(templates_dir),
				autoescape=select_autoescape(["html", "xml"]),
			)
			template = submodule_env.get_template("index.html")
			return template.render(
				module_name=name,
				modules=[],
				show_nav=False,
				show_home_about=False,
				embedded_mode=False,
				module_base_path=f"/module/{name}/app",
				request=request,
				url_for=url_for,
			)

		@flask_app.route("/module/<name>/app/static/<path:filename>")
		def module_static(name, filename):
			if name not in module_names:
				abort(404)

			static_dir = os.path.join(self.src_dir, "modules", name, "www", "static")
			if not os.path.isdir(static_dir):
				abort(404)
			return send_from_directory(static_dir, filename)

		@flask_app.route("/static/<path:filename>")
		def app_static(filename):
			static_dir = os.path.join(self.src_dir, "www", "static")
			if not os.path.isdir(static_dir):
				abort(404)
			return send_from_directory(static_dir, filename)

		return flask_app
