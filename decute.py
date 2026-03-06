import ast
import sys
from typing import Any

NOAST = ast.Module([], [])

counters = {}


def is_name(dat: str):
    for c in dat:
        if ord(c) > 10000:
            return False

    return True


def gen_name(pref: str):
    global counters
    c = counters.setdefault(pref, 0)
    counters["pref"] += 1
    return f"{pref}_{c}_DEOBF"


badfuncs = (
    "__runtime_check__",
    "__identity_func__",
    "__runtime_protect__",
    "__validate_signature__",
)

badclasses = (
    "__UltraProtection__",
    "__VMDetector__",
    "__ProtectionLayer__",
)


def deInt(wt):
    exx = bytearray(wt[len(b"0xFFFFFFFF/") :])
    tmp = 0
    for i in exx:
        tmp = tmp * 256 + i
    return tmp


def deInt2(a):
    return int(a - 309485009821345068724781055)


def deStr(arg):
    dat = (
        arg
        - 3333333333333333333333333333333333333333333333333333333333242422222222222222222722222233
    )
    if dat <= 127:
        return str(bytes([dat]), "utf8")
    elif dat <= 2047:
        return str(bytes([192 | dat >> 6, 128 | dat & 63]), "utf8")
    elif dat <= 65535:
        return str(
            bytes([224 | dat >> 12, 128 | dat >> 6 & 63, 128 | dat & 63]), "utf8"
        )
    else:
        return str(
            bytes(
                [
                    240 | dat >> 18,
                    128 | dat >> 12 & 63,
                    128 | dat >> 6 & 63,
                    128 | dat & 63,
                ]
            ),
            "utf8",
        )


def fixJoin(a, *_):
    mm = ""
    for item in a:
        mm += str(item)
    return mm


class DeCuteCFF(ast.NodeTransformer):
    def __init__(self, excname: str) -> None:
        self.exc = excname
        self.susp = set()
        self.detected = set()

    def visit_Try(self, node: ast.Try) -> Any:
        if (
            len(node.body) == 1
            and isinstance(node.body[0], ast.Raise)
            and isinstance(node.body[0].exc, ast.Call)
            and isinstance(node.body[0].exc.func, ast.Name)
            and node.body[0].exc.func.id == self.exc
            and len(node.handlers) == 1
            and len(node.handlers[0].body) > 0
        ):
            decffed = []
            for iif in node.handlers[0].body:
                if (
                    isinstance(iif, ast.If)
                    and isinstance(iif.test, ast.Compare)
                    and len(iif.test.comparators) == 1
                    and isinstance(iif.test.comparators[0], ast.Constant)
                    and iif.test.comparators[0].value == 1
                ):
                    for st in iif.body:
                        decffed.append(st)

            return self.generic_visit(ast.Module(decffed, []))
        return self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> Any:
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id == "obf_data_list":
                return NOAST
            elif isinstance(node.value, ast.Constant) and node.value.value == 0:
                self.susp.add(node.targets[0].id)

        return self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> Any:
        if isinstance(node.target, ast.Name) and node.target.id in self.susp:
            self.susp.remove(node.target.id)
            self.detected.add(node.target.id)
        return self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> Any:
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in badclasses
        ):
            return ast.Pass()
        return self.generic_visit(node)


class DeCuteNaming(ast.NodeTransformer):
    def __init__(self) -> None:
        self.remap = {}
        self.inlines = {}

    def visit_Import(self, node: ast.Import) -> Any:
        for alias in node.names:
            if alias.asname is not None:
                self.remap[alias.asname] = alias.name
                alias.asname = None

        return self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
        for alias in node.names:
            if alias.asname is not None:
                self.remap[alias.asname] = alias.name
                alias.asname = None

        return self.generic_visit(node)

    def visit_Name(self, node: ast.Name):
        node.id = self.remap.get(node.id, node.id)
        if node.id in self.inlines:
            return self.generic_visit(self.inlines[node.id])
        return self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> Any:
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if isinstance(node.value, ast.Name):
                self.remap[node.targets[0].id] = node.value.id
                return NOAST
            elif (
                isinstance(node.value, ast.Constant) and node.value.value == "utf8"
            ) or (
                isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)
                and node.value.func.id == "globals"
            ):
                self.inlines[node.targets[0].id] = node.value
                return NOAST

            # elif not is_name(node.targets[0].id):
            #     name = gen_name()
            #     self.remap[node.targets[0].id] = name
            #     node.targets[0].id = name

        return self.generic_visit(node)


class NoStupidLambda(ast.NodeTransformer):
    def visit_Call(self, node: ast.Call) -> Any:
        if isinstance(node.func, ast.Lambda) and isinstance(
            node.func.body, ast.Constant
        ):
            return node.func.body

        return self.generic_visit(node)


class DeCuteConst(ast.NodeTransformer):
    def __init__(self) -> None:
        self.inlinec = {
            "deint": ("", print),
            "destr": ("", print),
            "deint2": ("", print),
            "fixjoin": ("", print),
        }

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        if (
            len(node.body) == 4
            and isinstance(node.body[0], ast.Assign)
            and len(node.body[0].targets) == 1
            and isinstance(node.body[0].value, ast.Call)
            and isinstance(node.body[1], ast.Assign)
            and isinstance(node.body[1].value, ast.Constant)
            and len(node.body[1].targets) == 1
            and isinstance(node.body[1].targets[0], ast.Name)
            and isinstance(node.body[2], ast.For)
            and isinstance(node.body[3], ast.Return)
        ):
            self.inlinec["deint"] = (node.name, deInt)  # type: ignore
            return NOAST
        elif (
            len(node.body) == 1
            and isinstance(node.body[0], ast.Return)
            and isinstance(node.body[0].value, ast.Call)
            and isinstance(node.body[0].value.func, ast.Name)
            and node.body[0].value.func.id == "int"
            and len(node.body[0].value.args) == 1
            and isinstance(node.body[0].value.args[0], ast.BinOp)
            and isinstance(node.body[0].value.args[0].right, ast.Constant)
            and node.body[0].value.args[0].right.value == 309485009821345068724781055
        ):
            self.inlinec["deint2"] = (node.name, deInt2)  # type: ignore
            return NOAST
        elif (
            len(node.body) == 2
            and isinstance(node.body[0], ast.Assign)
            and len(node.body[0].targets) == 1
            and isinstance(node.body[0].value, ast.BinOp)
            and isinstance(node.body[0].value.right, ast.Constant)
            and node.body[0].value.right.value
            == 3333333333333333333333333333333333333333333333333333333333242422222222222222222722222233
            and isinstance(node.body[1], ast.If)
            and isinstance(node.body[1].test, ast.Compare)
            and len(node.body[1].test.comparators) == 1
            and isinstance(node.body[1].test.comparators[0], ast.Constant)
            and node.body[1].test.comparators[0].value == 127
        ):
            self.inlinec["destr"] = (node.name, deStr)  # type: ignore
            return NOAST
        elif (
            len(node.body) == 3
            and isinstance(node.body[0], ast.Assign)
            and len(node.body[0].targets) == 1
            and isinstance(node.body[0].value, ast.Constant)
            and node.body[0].value.value == ""
            and isinstance(node.body[1], ast.For)
            and isinstance(node.body[2], ast.Return)
            and isinstance(node.body[2].value, ast.Name)
        ):
            self.inlinec["fixjoin"] = (node.name, fixJoin)  # type: ignore
            return NOAST
        return self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> Any:
        inlines = tuple(map(lambda x: x[0], self.inlinec.values()))
        if isinstance(node.func, ast.Name) and node.func.id in inlines:
            if (
                len(node.args) == 1
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.func, ast.Name)
                and node.func.id == self.inlinec["deint"][0]
            ):
                return ast.Constant(self.inlinec["deint"][1](node.args[0].value))
            if (
                len(node.args) == 1
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.func, ast.Name)
                and node.func.id == self.inlinec["deint2"][0]
            ):
                return ast.Constant(self.inlinec["deint2"][1](node.args))
            elif (
                len(node.args) == 1
                and isinstance(node.args[0], ast.Call)
                and isinstance(node.args[0].func, ast.Name)
                and isinstance(node.func, ast.Name)
                and node.func.id == self.inlinec["fixjoin"][0]
                and node.args[0].func.id == "list"
                and len(node.args[0].args) == 1
                and isinstance(node.args[0].args[0], ast.Call)
                and isinstance(node.args[0].args[0].func, ast.Name)
                and node.args[0].args[0].func.id == "map"
                and len(node.args[0].args[0].args) == 2
                and isinstance(node.args[0].args[0].args[0], ast.Name)
                and node.args[0].args[0].args[0].id == self.inlinec["destr"][0]
            ):
                return ast.Constant(
                    eval(
                        ast.unparse(node)
                        .replace(self.inlinec["fixjoin"][0], "fixJoin")
                        .replace(self.inlinec["destr"][0], "deStr")
                    )
                )
        return self.generic_visit(node)


class DeCuteCFFPost(ast.NodeTransformer):
    def __init__(self, detected: set[str]) -> None:
        self.detected = detected

    def visit_Assign(self, node: ast.Assign) -> Any:
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in self.detected:
                return NOAST

        return self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> Any:
        if isinstance(node.target, ast.Name):
            if node.target.id in self.detected:
                return NOAST

        return self.generic_visit(node)


class Fixer(ast.NodeTransformer):
    def visit_Try(self, node: ast.Try) -> Any:
        if len(node.body) == 1 and isinstance(node.body[0], ast.Module):
            node.body = [ast.Pass()]
        return self.generic_visit(node)


def astfix(obj: ast.AST):
    return ast.parse(ast.unparse(Fixer().visit(obj)))


def deobf(src: str) -> str:
    ast_s = ast.parse(src)
    first = ast_s.body[0]
    if not isinstance(first, ast.ClassDef):
        return "# error: first stmt is not class"

    ast_s.body[0] = NOAST  # type: ignore
    exc: ast.ClassDef = first

    # удаление лишних функций далбаепских
    ast_s.body = list(
        filter(
            lambda st: not (isinstance(st, ast.FunctionDef) and st.name in badfuncs),
            ast_s.body,
        )
    )

    # удаление лишних классов супер ультра ультимейт протектиан
    ast_s.body = list(
        filter(
            lambda st: not (isinstance(st, ast.ClassDef) and st.name in badclasses),
            ast_s.body,
        )
    )

    decff = DeCuteCFF(excname=exc.name)
    out = astfix(decff.visit(ast_s))

    post = DeCuteCFFPost(decff.detected)
    out = post.visit(out)

    decname = DeCuteNaming()
    out = astfix(decname.visit(out))

    decconst = DeCuteConst()
    out = astfix(NoStupidLambda().visit(decconst.visit(out)))

    # чистка лишних мусаров
    out.body = list(
        filter(
            lambda st: (
                not (
                    isinstance(st, ast.Try)
                    and len(st.body) == 1
                    and isinstance(st.body[0], ast.Pass)
                )
            ),
            out.body,
        )
    )
    out.body = list(
        filter(
            lambda st: (
                not (
                    isinstance(st, ast.Try)
                    and len(st.body) == 2
                    and isinstance(st.body[0], ast.Import)
                    and st.body[0].names[0].name == "__main__"
                )
            ),
            out.body,
        )
    )

    out.body = list(
        filter(
            lambda st: (
                not (
                    isinstance(st, ast.Try)
                    and len(st.body) == 2
                    and isinstance(st.body[0], ast.Assign)
                    and isinstance(st.body[0].targets[0], ast.Name)
                    and st.body[0].targets[0].id.startswith("__")
                    and st.body[0].targets[0].id.endswith("__")
                )
            ),
            out.body,
        )
    )

    out.body = list(
        filter(
            lambda st: (
                not (
                    isinstance(st, ast.Try)
                    and len(st.body) == 3
                    and isinstance(st.body[0], ast.FunctionDef)
                    and st.body[0].name == "__decoder__"
                )
            ),
            out.body,
        )
    )

    return ast.unparse(out)


def main(args: list[str]):
    if len(args) > 3 or len(args) < 2:
        print("# usage:")
        print(f"# \tjust write output to console: {args[0]} <obfuscated>")
        print(f"# \tsave deobfuscated: {args[0]} <obfuscated> deobf.py")
        return

    if len(args) == 3:
        sys.stdout = open(args[2], "w", encoding="utf-8")

    file = args[1]
    with open(file, "rb") as f:
        src = f.read().decode()

    print(deobf(src))


if __name__ == "__main__":
    main(sys.argv)
