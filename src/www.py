"""
file: www.py
description: pyqmh Sequencer for developing the editor and test executive
author: Larry
"""

import json
import logging
import os
import threading

from flask import Flask, abort, jsonify, redirect, render_template, request, send_from_directory, url_for
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pyqmh import Protocol


class WebGui:
	"""Owns Flask app setup, routes, and server startup for the main app."""

	def __init__(self, logger: logging.Logger, protocol: Protocol):
		self.logger = logger
		self.protocol = protocol
		self.src_dir = os.path.dirname(__file__)
		self._routes_config = self._load_routes_config()
		self.flask_app = self._create_flask_app()

	def start(self) -> threading.Thread:
		"""Start the Flask server in a background daemon thread."""
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
		"""Load optional routes.json from the app directory."""
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

	def _discover_nested_module_web_apps(self, module_name: str) -> list:
		module_modules_dir = os.path.join(self.src_dir, "modules", module_name, "modules")
		if not os.path.isdir(module_modules_dir):
			return []

		result = []
		for name in sorted(os.listdir(module_modules_dir)):
			if name.startswith("_"):
				continue
			www_path = os.path.join(module_modules_dir, name, "www")
			if os.path.isdir(www_path):
				result.append(name)
		return result

	def _module_has_about_page(self, module_name: str) -> bool:
		about_file = os.path.join(self.src_dir, "modules", module_name, "www", "templates", "about.html")
		return os.path.isfile(about_file)

	def _path_is_active(self, current_path: str, target_path: str) -> bool:
		if target_path == "/":
			return current_path == "/"
		return current_path == target_path or current_path.startswith(target_path + "/")

	def _build_nav_items_from_routes(self, current_path: str) -> list:
		nav_items = []
		for label, value in self._routes_config.items():
			if str(label).lower() == "modules":
				if not isinstance(value, dict):
					continue

				dropdown_items = []
				for module_label, module_path in value.items():
					if not isinstance(module_label, str) or not isinstance(module_path, str):
						continue
					dropdown_items.append(
						{
							"label": module_label,
							"path": module_path,
							"active": self._path_is_active(current_path, module_path),
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
			nav_items.append(
				{
					"type": "link",
					"label": label,
					"path": value,
					"active": self._path_is_active(current_path, value),
				}
			)

		return nav_items

	def _build_default_nav_items(self, module_names: list, current_path: str) -> list:
		nav_items = [{"type": "link", "label": "Home", "path": "/", "active": current_path == "/"}]

		if module_names:
			dropdown_items = []
			for module in module_names:
				module_path = f"/module/{module}"
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

		nav_items.append(
			{
				"type": "link",
				"label": "About",
				"path": "/about",
				"active": self._path_is_active(current_path, "/about"),
			}
		)
		return nav_items

	def _build_nav_items(self, module_names: list, current_path: str) -> list:
		if self._routes_config:
			return self._build_nav_items_from_routes(current_path)
		return self._build_default_nav_items(module_names, current_path)

	def _build_embedded_module_nav_items(self, nested_modules: list, module_base_path: str, current_path: str) -> list:
		if not nested_modules:
			return []

		dropdown_items = []
		for module in nested_modules:
			module_path = f"{module_base_path}/module/{module}"
			dropdown_items.append(
				{
					"label": module.replace("_", " ").title(),
					"path": module_path,
					"active": self._path_is_active(current_path, module_path),
				}
			)

		return [
			{
				"type": "dropdown",
				"label": "Modules",
				"items": dropdown_items,
				"active": any(item["active"] for item in dropdown_items),
			}
		]

	def _create_flask_app(self) -> Flask:
		flask_app = Flask(
			__name__,
			template_folder=os.path.join(self.src_dir, "www", "templates"),
			static_folder=os.path.join(self.src_dir, "www", "static"),
		)

		module_names = self._discover_module_web_apps()

		@flask_app.route("/")
		def index():
			return render_template("index.html", modules=module_names, nav_items=self._build_nav_items(module_names, request.path))

		@flask_app.route("/about")
		def about():
			modules_with_about = [module for module in module_names if self._module_has_about_page(module)]
			return render_template(
				"about.html",
				modules=module_names,
				modules_with_about=modules_with_about,
				nav_items=self._build_nav_items(module_names, request.path),
			)

		@flask_app.route("/module/<name>")
		def module_page(name):
			if name in module_names:
				return render_template(
					"module_page.html",
					module_name=name,
					modules=module_names,
					nav_items=self._build_nav_items(module_names, request.path),
				)
			return redirect(url_for("index"))

		@flask_app.route("/module/<name>/app/")
		@flask_app.route("/module/<name>/app/index")
		def module_app(name):
			if name not in module_names:
				return redirect(url_for("index"))

			templates_dir = os.path.join(self.src_dir, "modules", name, "www", "templates")
			index_file = os.path.join(templates_dir, "index.html")
			if not os.path.isfile(index_file):
				abort(404)

			nested_modules = self._discover_nested_module_web_apps(name)
			module_base_path = f"/module/{name}/app"
			nav_items = self._build_embedded_module_nav_items(nested_modules, module_base_path, request.path)

			module_env = Environment(
				loader=FileSystemLoader(templates_dir),
				autoescape=select_autoescape(["html", "xml"]),
			)
			template = module_env.get_template("index.html")
			return template.render(
				module_name=name,
				modules=nested_modules,
				show_nav=bool(nav_items),
				show_home_about=False,
				embedded_mode=True,
				module_base_path=module_base_path,
				nav_items=nav_items,
				request=request,
				url_for=url_for,
			)

		@flask_app.route("/module/<name>/app/about")
		def module_about(name):
			if name not in module_names:
				return redirect(url_for("index"))

			templates_dir = os.path.join(self.src_dir, "modules", name, "www", "templates")
			about_file = os.path.join(templates_dir, "about.html")
			if not os.path.isfile(about_file):
				return redirect(url_for("module_page", name=name))

			nested_modules = self._discover_nested_module_web_apps(name)
			module_base_path = f"/module/{name}/app"
			nav_items = self._build_embedded_module_nav_items(nested_modules, module_base_path, request.path)

			module_env = Environment(
				loader=FileSystemLoader(templates_dir),
				autoescape=select_autoescape(["html", "xml"]),
			)
			template = module_env.get_template("about.html")
			return template.render(
				module_name=name,
				modules=nested_modules,
				show_nav=bool(nav_items),
				show_home_about=False,
				embedded_mode=True,
				module_base_path=module_base_path,
				nav_items=nav_items,
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

		@flask_app.post("/module/<name>/app/api/action")
		def module_action(name):
			if name not in module_names:
				return jsonify({"ok": False, "error": f"Unknown module '{name}'"}), 404

			body = request.get_json(silent=True) or {}
			action = body.get("action")
			arguments = body.get("arguments", {})
			if not isinstance(action, str) or not action:
				return jsonify({"ok": False, "error": "Missing action"}), 400
			if not isinstance(arguments, dict):
				return jsonify({"ok": False, "error": "arguments must be an object"}), 400

			try:
				self.protocol.send_action(name, action, payload=arguments)
				return jsonify({"ok": True, "action": action, "module": name})
			except Exception as exc:
				self.logger.exception("Failed action %s on %s", action, name)
				return jsonify({"ok": False, "error": str(exc)}), 500

		@flask_app.post("/module/<name>/app/api/request")
		def module_request(name):
			if name not in module_names:
				return jsonify({"ok": False, "error": f"Unknown module '{name}'"}), 404

			body = request.get_json(silent=True) or {}
			action = body.get("action")
			arguments = body.get("arguments", {})
			timeout_ms = body.get("timeout_ms", 1000)
			if not isinstance(action, str) or not action:
				return jsonify({"ok": False, "error": "Missing action"}), 400
			if not isinstance(arguments, dict):
				return jsonify({"ok": False, "error": "arguments must be an object"}), 400

			try:
				timeout_s = max(0.05, float(timeout_ms) / 1000.0)
			except (TypeError, ValueError):
				timeout_s = 1.0

			try:
				response = self.protocol.send_request(name, action, payload=arguments, timeout=timeout_s)
				return jsonify({"ok": True, "action": action, "module": name, "response": response})
			except TimeoutError:
				return jsonify({"ok": False, "error": "Request timed out"}), 504
			except Exception as exc:
				self.logger.exception("Failed request %s on %s", action, name)
				return jsonify({"ok": False, "error": str(exc)}), 500

		@flask_app.route("/module/<name>/app/module/<sub_name>")
		@flask_app.route("/module/<name>/app/module/<sub_name>/app/")
		@flask_app.route("/module/<name>/app/module/<sub_name>/app/index")
		def nested_module_app(name, sub_name):
			if name not in module_names:
				return redirect(url_for("index"))

			nested_modules = self._discover_nested_module_web_apps(name)
			if sub_name not in nested_modules:
				return redirect(url_for("module_app", name=name))

			templates_dir = os.path.join(self.src_dir, "modules", name, "modules", sub_name, "www", "templates")
			index_file = os.path.join(templates_dir, "index.html")
			if not os.path.isfile(index_file):
				abort(404)

			submodule_env = Environment(
				loader=FileSystemLoader(templates_dir),
				autoescape=select_autoescape(["html", "xml"]),
			)
			template = submodule_env.get_template("index.html")
			return template.render(
				module_name=sub_name,
				modules=[],
				show_nav=False,
				show_home_about=False,
				embedded_mode=True,
				module_base_path=f"/module/{name}/app/module/{sub_name}/app",
				request=request,
				url_for=url_for,
			)

		@flask_app.route("/module/<name>/app/module/<sub_name>/app/static/<path:filename>")
		def nested_module_static(name, sub_name, filename):
			if name not in module_names:
				abort(404)

			nested_modules = self._discover_nested_module_web_apps(name)
			if sub_name not in nested_modules:
				abort(404)

			static_dir = os.path.join(self.src_dir, "modules", name, "modules", sub_name, "www", "static")
			if not os.path.isdir(static_dir):
				abort(404)
			return send_from_directory(static_dir, filename)

		return flask_app
