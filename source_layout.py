#!/usr/bin/env python

import argparse
import ast
from dataclasses import dataclass
import glob
import logging
import os
from typing import List, Optional, Union
from enum import Enum


class StrEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class Issue:
    def __init__(self, line: int, msg: str):
        self.line = line
        self.msg = msg

    def __repr__(self):
        return f"Issue(line={self.line}, msg={self.msg})"


class DeclType(Enum):
    ROOT = 0
    IMPORT = 1
    CLASS_DECL = 2
    CLASS_VAR = 3
    MAGIC_METHOD = 4
    STATIC_METHOD = 5
    GETTER_SETTER = 6
    PUBLIC_METHOD = 7
    PRIVATE_METHOD = 8


class DeclNode:
    def __init__(self, decl_type: DeclType, name: str, line: int):
        self.decl_type: DeclType = decl_type
        self.name: str = name
        self.children: List[DeclNode] = []
        self.line: int = line

    def __repr__(self):
        return f"DeclTree({self.decl_type}, {self.name})"

    def add_child(self, child: "DeclNode"):
        self.children.append(child)

    def check_order(self) -> List[Issue]:
        prev: Optional[DeclNode] = None
        issues: List[Issue] = []
        for child in self.children:
            if prev is None:
                prev = child
                continue
            if child.decl_type.value < prev.decl_type.value:
                issues.append(
                    Issue(
                        child.line, f'"{child.name}" should not be after "{prev.name}"'
                    )
                )
            prev = child
        for child in self.children:
            child_issues = child.check_order()
            issues.extend(child_issues)

        return issues

    def pretty_print(self, indent: int = 0) -> str:
        lines = []
        lines.append(
            f"{' ' * indent}{self.line} {self.decl_type.value} {self.decl_type.name.lower()} {self.name}"
        )
        for child in self.children:
            lines.append(child.pretty_print(indent + 4))
        return "\n".join(lines)


class Analyzer:
    def __init__(self, path: str):
        self.path = path

    @staticmethod
    def process(path: str) -> List[Issue]:
        return Analyzer(path)._analyze_file(path)  # pylint: disable=protected-access

    def _analyze_module(self, module: ast.Module) -> DeclNode:
        decl_tree = DeclNode(DeclType.ROOT, "root", 0)
        for i, node in enumerate(module.body):
            if isinstance(node, ast.ClassDef):
                decl_tree.add_child(self._analyze_class(node))
            elif isinstance(node, ast.FunctionDef):
                decl_tree.add_child(self._analyze_function(node))
            elif isinstance(node, ast.Import):
                decl_tree.add_child(self._analyze_import(node))
            else:
                # logging.debug("skip module line %s:%s %s", self.path, node.lineno, node)
                pass
        return decl_tree

    def _analyze_import(self, node: ast.Import) -> DeclNode:
        names: List[str] = []
        for alias in node.names:
            names.append(alias.name)
        return DeclNode(DeclType.IMPORT, ",".join(names), node.lineno)

    def _analyze_class(self, node: ast.ClassDef) -> DeclNode:
        decl_tree = DeclNode(DeclType.CLASS_DECL, node.name, node.lineno)
        for i, child in enumerate(node.body):
            if isinstance(child, ast.Assign):
                decl_tree.add_child(self._analyze_class_var(child))
            elif isinstance(child, ast.FunctionDef):
                decl_tree.add_child(self._analyze_function(child))
            elif isinstance(child, ast.AnnAssign):
                decl_tree.add_child(self._analyze_class_var(child))
            else:
                # logging.debug(
                #     "skip class line %s:%s %s", self.path, child.lineno, child
                # )
                pass

        return decl_tree

    def _analyze_class_var(self, node: Union[ast.AnnAssign, ast.Assign]) -> DeclNode:
        if isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                name = node.target.id
            elif isinstance(node.target, ast.Attribute):
                name = node.target.attr
            else:
                name = "unknown"
            return DeclNode(DeclType.CLASS_VAR, name, node.lineno)
        if isinstance(node, ast.Assign):
            if len(node.targets) == 0:
                name = "unknown"
            elif isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
            elif isinstance(node.targets[0], ast.Attribute):
                name = node.targets[0].attr
            else:
                name = "unknown"
            return DeclNode(DeclType.CLASS_VAR, name, node.lineno)

    def _analyze_function(self, node: ast.FunctionDef) -> DeclNode:
        if len(node.decorator_list) > 0:
            if isinstance(node.decorator_list[0], ast.Name):
                if node.decorator_list[0].id == "staticmethod":
                    return DeclNode(DeclType.STATIC_METHOD, node.name, node.lineno)
                # property
                if node.decorator_list[0].id == "property":
                    return DeclNode(DeclType.GETTER_SETTER, node.name, node.lineno)
            # also treat @xx.setter as property
            if isinstance(node.decorator_list[0], ast.Attribute):
                if node.decorator_list[0].attr == "setter":
                    return DeclNode(DeclType.GETTER_SETTER, node.name, node.lineno)
        if node.name.startswith("__") and node.name.endswith("__"):
            return DeclNode(DeclType.MAGIC_METHOD, node.name, node.lineno)
        if node.name.startswith("_"):
            return DeclNode(DeclType.PRIVATE_METHOD, node.name, node.lineno)

        return DeclNode(DeclType.PUBLIC_METHOD, node.name, node.lineno)

    def _analyze_file(self, path: str) -> List[Issue]:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()

        try:
            module = ast.parse(text)
        except Exception as ex:
            logging.error("failed to parse %s: %s", path, ex)
            return []
        decl_tree = self._analyze_module(module)
        logging.debug("Declaration tree (LINE | NAME):")
        logging.debug(decl_tree.pretty_print())
        return decl_tree.check_order()


if __name__ == "__main__":

    @dataclass
    class _Args:
        path: str
        verbose: bool

    class Colors(StrEnum):
        GREY = "\x1b[38;20m"
        YELLOW = "\x1b[33;20m"
        RED = "\x1b[31;20m"
        BOLD_RED = "\x1b[31;1m"
        RESET = "\x1b[0m"

    class CustomFormatter(logging.Formatter):
        format_ = (
            # "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"
            "%(message)s"
        )

        FORMATS = {
            logging.DEBUG: Colors.GREY + format_ + Colors.RESET,
            logging.INFO: Colors.GREY + format_ + Colors.RESET,
            logging.WARNING: Colors.YELLOW + format_ + Colors.RESET,
            logging.ERROR: Colors.RED + format_ + Colors.RESET,
            logging.CRITICAL: Colors.BOLD_RED + format_ + Colors.RESET,
        }

        def format(self, record):
            log_fmt = self.FORMATS.get(record.levelno)
            formatter = logging.Formatter(log_fmt)
            return formatter.format(record)

    def handle_issues(file: str, issues: List[Issue]):
        if len(issues) == 0:
            return
        logging.error("Found issues in %s:", file)
        for issue in issues:
            # print(f"    {file}:{issue.line} {issue.msg}")
            logging.info("    %s:%s %s", file, issue.line, issue.msg)

    def parse_args() -> _Args:
        parser = argparse.ArgumentParser(
            description="A static analysis tool that checks the order of python code layout."
        )
        parser.add_argument("path", type=str, help="path to scan")
        parser.add_argument(
            "-v", "--verbose", action="store_true", help="verbose output"
        )
        args = parser.parse_args()
        return _Args(**vars(args))

    def init_logger():
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(CustomFormatter())
        default_logger = logging.getLogger()
        default_logger.setLevel(
            logging.INFO if not parse_args().verbose else logging.DEBUG
        )
        default_logger.addHandler(ch)

    def main():
        init_logger()
        args = parse_args()
        if os.path.isfile(args.path):
            files = [args.path]
        else:
            args.path = args.path.rstrip("/")
            files = glob.glob(f"{args.path}/**/*.py", recursive=True)
        for path in files:
            issues = Analyzer.process(path)
            handle_issues(path, issues)

    main()
