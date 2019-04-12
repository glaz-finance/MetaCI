import factory
import factory.fuzzy

import numbers
import random

from metaci.plan.models import Plan, PlanRepository
from metaci.testresults.models import TestResult, TestMethod, TestClass
from metaci.build.models import BuildFlow, Build, BUILD_STATUSES, BUILD_FLOW_STATUSES
from metaci.repository.models import Branch, Repository

from metaci.users.models import User

BUILD_STATUS_NAMES = (name for (name, label) in BUILD_STATUSES)
BUILD_FLOW_STATUS_NAMES = (name for (name, label) in BUILD_FLOW_STATUSES)


def do_logs():
    import logging

    logger = logging.getLogger("factory")
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.DEBUG)


def fake_name(prefix=None):
    return factory.LazyAttribute(
        lambda a: (getattr(a, "_name_prefix", None) or prefix or "")
        + factory.Faker("word").generate({})
    )


class RelatedFactoryList(factory.RelatedFactory):
    """Calls a factory 'size' times once the object has been generated.
        Simplified from
        https://github.com/FactoryBoy/factory_boy/blob/2481d411cde311bb7edd51b6dff3b345c2c14bc6/factory/declarations.py#L675
        While awaiting release
    """

    def __init__(self, factory, factory_related_name="", size=2, **defaults):
        self.size = size
        super(RelatedFactoryList, self).__init__(
            factory, factory_related_name, **defaults
        )

    def call(self, instance, step, context):
        return [
            super(RelatedFactoryList, self).call(instance, step, context)
            for i in range(self.size if isinstance(self.size, int) else self.size())
        ]


class PlanFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Plan

    _name_prefix = "Plan"
    name = fake_name()


class RepositoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Repository
        exclude = ("_name_prefix",)

    name = fake_name()

    github_id = 1234
    _name_prefix = "Repo_"
    owner = factory.fuzzy.FuzzyChoice(["SFDO", "SFDC", "Partner1", "Partner2"])

    # @factory.post_generation
    # def postgen(obj, create, extracted, **kwargs):
    #     if not obj.repo:
    #         obj.repo = factory.fuzzy.FuzzyChoice(Repository.objects.all())

    #     if not len(obj.builds) > 0:
    #         for i in range(0, 7):
    #             BuildFactory(repo=obj)


class PlanRepositoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PlanRepository

    plan = factory.fuzzy.FuzzyChoice(Plan.objects.all())
    repo = factory.SubFactory(RepositoryFactory)


class BranchFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Branch

    name = factory.fuzzy.FuzzyChoice(["master", "branch1", "branch2"])

    @factory.post_generation
    def postgen(obj, create, extracted, **kwargs):
        if not obj.repo:
            obj.repo = random.choice(Repository.objects.all())
            obj.save()


class BuildFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Build

    planrepo = factory.SubFactory(PlanRepositoryFactory)
    plan = factory.LazyAttribute(lambda build: build.planrepo.plan)
    repo = factory.LazyAttribute(lambda build: build.planrepo.repo)
    branch = factory.LazyAttribute(
        lambda build: BranchFactory(repo=build.planrepo.repo)
    )
    status = factory.fuzzy.FuzzyChoice(BUILD_STATUS_NAMES)


class BuildFlowFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BuildFlow

    tests_total = 1
    build = factory.SubFactory(BuildFactory)

    flow = factory.fuzzy.FuzzyChoice(["rida", "andebb", "ttank", "tleft"])
    status = factory.fuzzy.FuzzyChoice(BUILD_FLOW_STATUS_NAMES)


class TestClassFactory(factory.django.DjangoModelFactory):
    __test__ = False  # PyTest is confused by the classname

    class Meta:
        model = TestClass
        exclude = ("_name_prefix",)

    _name_prefix = "Test_"
    repo = factory.LazyAttribute(lambda x: random.choice(Repository.objects.all()))
    name = fake_name()


class TestMethodFactory(factory.django.DjangoModelFactory):
    __test__ = False  # PyTest is confused by the classname

    class Meta:
        model = TestMethod
        exclude = ("_name_prefix",)

    _name_prefix = "Test_"
    testclass = factory.SubFactory(TestClassFactory)
    name = fake_name()

    @factory.post_generation
    def _target_success_setter(obj, create, extracted=None, **kwargs):
        if isinstance(extracted, numbers.Number):
            obj._target_success_pct = extracted
        else:
            obj._target_success_pct = random.random() * 100
        obj.save()


class TestResultFactory(factory.django.DjangoModelFactory):
    __test__ = False  # PyTest is confused by the classname

    class Meta:
        model = TestResult
        exclude = ("target_success_rate",)

    build_flow = factory.SubFactory(BuildFlowFactory)
    method = factory.SubFactory(TestMethodFactory)
    duration = factory.fuzzy.FuzzyFloat(2, 10000)

    @factory.LazyAttribute
    def outcome(result):
        success = random.random() * 100 < result.method._target_success_pct
        if success:
            return "success"
        else:
            return random.choice(["CompileFail", "Fail", "Skip"])


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("username",)

    email = factory.Sequence("user_{}@example.com".format)
    username = factory.Sequence("user_{}@example.com".format)
    password = factory.PostGenerationMethodCall("set_password", "foobar")


class StaffSuperuserFactory(UserFactory):
    is_staff = True
    is_superuser = True
