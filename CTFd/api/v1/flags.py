import json
from typing import List

from flask import request
from flask_restx import Namespace, Resource

from CTFd.api.v1.helpers.request import validate_args
from CTFd.api.v1.helpers.schemas import sqlalchemy_to_pydantic
from CTFd.api.v1.schemas import APIDetailedSuccessResponse, APIListSuccessResponse
from CTFd.constants import RawEnum
from CTFd.models import Flags, db
from CTFd.plugins.flags import (
    FLAG_CLASSES,
    CTFdDynamicFlag,
    FlagException,
    agent_prompt,
    dynamic,
    get_flag_class,
)
from CTFd.schemas.flags import FlagSchema
from CTFd.utils import get_config
from CTFd.utils.decorators import admins_only
from CTFd.utils.helpers.models import build_model_filters

flags_namespace = Namespace("flags", description="Endpoint to retrieve Flags")

FlagModel = sqlalchemy_to_pydantic(Flags)


class FlagDetailedSuccessResponse(APIDetailedSuccessResponse):
    data: FlagModel


class FlagListSuccessResponse(APIListSuccessResponse):
    data: List[FlagModel]


flags_namespace.schema_model(
    "FlagDetailedSuccessResponse", FlagDetailedSuccessResponse.apidoc()
)

flags_namespace.schema_model(
    "FlagListSuccessResponse", FlagListSuccessResponse.apidoc()
)


@flags_namespace.route("")
class FlagList(Resource):
    @admins_only
    @flags_namespace.doc(
        description="Endpoint to list Flag objects in bulk",
        responses={
            200: ("Success", "FlagListSuccessResponse"),
            400: (
                "An error occured processing the provided or stored data",
                "APISimpleErrorResponse",
            ),
        },
    )
    @validate_args(
        {
            "challenge_id": (int, None),
            "type": (str, None),
            "content": (str, None),
            "data": (str, None),
            "q": (str, None),
            "field": (
                RawEnum(
                    "FlagFields", {"type": "type", "content": "content", "data": "data"}
                ),
                None,
            ),
        },
        location="query",
    )
    def get(self, query_args):
        q = query_args.pop("q", None)
        field = str(query_args.pop("field", None))
        filters = build_model_filters(model=Flags, query=q, field=field)

        flags = Flags.query.filter_by(**query_args).filter(*filters).all()
        schema = FlagSchema(many=True)
        response = schema.dump(flags)
        if response.errors:
            return {"success": False, "errors": response.errors}, 400

        return {"success": True, "data": response.data}

    @admins_only
    @flags_namespace.doc(
        description="Endpoint to create a Flag object",
        responses={
            200: ("Success", "FlagDetailedSuccessResponse"),
            400: (
                "An error occured processing the provided or stored data",
                "APISimpleErrorResponse",
            ),
        },
    )
    def post(self):
        req = request.get_json()
        schema = FlagSchema()

        if req.get("type") == "dynamic":
            try:
                req["data"] = CTFdDynamicFlag.prepare_data(req.get("data") or "")
            except FlagException as e:
                return {"success": False, "errors": {"data": [str(e)]}}, 400
        response = schema.load(req, session=db.session)

        if response.errors:
            return {"success": False, "errors": response.errors}, 400

        # We only want to operate on flag types where are have
        # high confidence a leading/trailing space was not intentional
        if response.data.type in ("static", "regex", "dynamic"):
            response.data.content = response.data.content.strip()

        db.session.add(response.data)
        db.session.commit()

        response = schema.dump(response.data)
        db.session.close()

        return {"success": True, "data": response.data}


@flags_namespace.route("/types")
class FlagTypes(Resource):
    @admins_only
    def get(self):
        response = {}
        for class_id in FLAG_CLASSES:
            flag_class = FLAG_CLASSES.get(class_id)
            response[class_id] = {
                "name": flag_class.name,
                "templates": flag_class.templates,
            }
        return {"success": True, "data": response}


@flags_namespace.route("/types/<type_name>")
class FlagType(Resource):
    @admins_only
    def get(self, type_name):
        flag_class = get_flag_class(type_name)
        response = {"name": flag_class.name, "templates": flag_class.templates}
        return {"success": True, "data": response}


@flags_namespace.route("/<flag_id>")
class Flag(Resource):
    @admins_only
    @flags_namespace.doc(
        description="Endpoint to get a specific Flag object",
        responses={
            200: ("Success", "FlagDetailedSuccessResponse"),
            400: (
                "An error occured processing the provided or stored data",
                "APISimpleErrorResponse",
            ),
        },
    )
    def get(self, flag_id):
        flag = Flags.query.filter_by(id=flag_id).first_or_404()
        schema = FlagSchema()
        response = schema.dump(flag)

        if response.errors:
            return {"success": False, "errors": response.errors}, 400

        response.data["templates"] = get_flag_class(flag.type).templates

        return {"success": True, "data": response.data}

    @admins_only
    @flags_namespace.doc(
        description="Endpoint to delete a specific Flag object",
        responses={200: ("Success", "APISimpleSuccessResponse")},
    )
    def delete(self, flag_id):
        flag = Flags.query.filter_by(id=flag_id).first_or_404()

        db.session.delete(flag)
        db.session.commit()
        db.session.close()

        return {"success": True}

    @admins_only
    @flags_namespace.doc(
        description="Endpoint to edit a specific Flag object",
        responses={
            200: ("Success", "FlagDetailedSuccessResponse"),
            400: (
                "An error occured processing the provided or stored data",
                "APISimpleErrorResponse",
            ),
        },
    )
    def patch(self, flag_id):
        flag = Flags.query.filter_by(id=flag_id).first_or_404()
        schema = FlagSchema()
        req = request.get_json()

        # We only want to operate on flag types where are have
        # high confidence a leading/trailing space was not intentional
        if flag.type in ("static", "regex", "dynamic") and req.get("content"):
            req["content"] = req["content"].strip()

        # Dynamic flags keep their stored key unless a new one is sent
        if req.get("type", flag.type) == "dynamic" and (
            "data" in req or flag.type != "dynamic"
        ):
            try:
                req["data"] = CTFdDynamicFlag.prepare_data(req.get("data") or "")
            except FlagException as e:
                return {"success": False, "errors": {"data": [str(e)]}}, 400

        response = schema.load(req, session=db.session, instance=flag, partial=True)

        if response.errors:
            return {"success": False, "errors": response.errors}, 400

        db.session.commit()

        response = schema.dump(response.data)
        db.session.close()

        return {"success": True, "data": response.data}


@flags_namespace.route("/agent-prompt")
class FlagAgentPrompt(Resource):
    @admins_only
    def post(self):
        """Build the AI-agent prompt for a dynamic flag from unsaved form values"""
        req = request.get_json() or {}
        data = req.get("data") or {}
        if isinstance(data, str):
            try:
                data = json.loads(data) if data.strip() else {}
            except ValueError:
                data = {}
        try:
            length = int(data.get("len") or dynamic.DEFAULT_LENGTH)
        except (ValueError, TypeError):
            length = dynamic.DEFAULT_LENGTH
        prompt = agent_prompt.build(
            req.get("content", ""),
            secret=(data.get("secret") or "").strip().lower(),
            length=length,
            bind=data.get("bind") or "team_name",
        )
        warnings = []
        if get_config("name_changes", default=True):
            warnings.append(
                "Teams can still rename themselves. A renamed team's dynamic flag "
                "stops working. Turn off 'Name changes' in Admin > Config > Accounts."
            )
        return {"success": True, "data": {"prompt": prompt, "warnings": warnings}}


@flags_namespace.route("/<flag_id>/preview")
class FlagPreview(Resource):
    @admins_only
    def get(self, flag_id):
        """Show the flag a given team/user must submit for a dynamic flag"""
        flag = Flags.query.filter_by(id=flag_id).first_or_404()
        if flag.type != "dynamic":
            return {"success": False, "errors": {"type": ["Not a dynamic flag"]}}, 400

        identity = request.args.get("identity", "").strip()
        if not identity:
            return {"success": False, "errors": {"identity": ["Enter a name"]}}, 400

        try:
            expected = CTFdDynamicFlag.expected(flag, identity)
        except Exception:
            return {
                "success": False,
                "errors": {"data": ["Flag is misconfigured"]},
            }, 400

        return {"success": True, "data": {"identity": identity, "flag": expected}}
