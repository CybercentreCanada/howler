import textwrap

from howler.cronjobs.rules import (
    create_correlated_bundle,
    create_executor,
    register_rules,
    setup_job,
)
from howler.odm.models.analytic import Analytic
from howler.odm.models.hit import Hit
from howler.odm.random_data import create_analytics, create_hits
from howler.odm.randomizer import random_model_obj


def test_correlated_bundle(datastore_connection):
    rule: Analytic = random_model_obj(Analytic)
    rule.rule = "howler.id:*"
    rule.rule_type = "lucene"
    rule.rule_crontab = "0 0 * * *"

    child_hits = [random_model_obj(Hit), random_model_obj(Hit)]

    correlated_bundle = create_correlated_bundle(rule, rule.rule, child_hits)

    datastore_connection.hit.commit()

    correlated_bundle_2 = create_correlated_bundle(rule, rule.rule, child_hits)

    correlated_bundle_3 = create_correlated_bundle(
        rule,
        rule.rule,
        [random_model_obj(Hit), random_model_obj(Hit)],
    )

    assert correlated_bundle.howler.analytic == rule.name
    assert correlated_bundle.howler.id == correlated_bundle_2.howler.id
    assert correlated_bundle_3.howler.id != correlated_bundle_2.howler.id


def test_registration(datastore_connection):
    from howler.cronjobs import scheduler

    create_analytics(datastore_connection, num_analytics=4)

    setup_job(scheduler)

    rule: Analytic = random_model_obj(Analytic)
    rule.rule = "howler.id:*"
    rule.rule_type = "lucene"
    rule.rule_crontab = "0 0 * * *"

    datastore_connection.analytic.save(rule.analytic_id, rule)

    register_rules(rule, test_override=True)

    register_rules(rule, test_override=True)

    register_rules(test_override=True)

    register_rules(test_override=True)

    assert scheduler.get_job(f"rule_{rule.analytic_id}")

    scheduler.remove_all_jobs()


def test_executor(datastore_connection):
    create_hits(datastore_connection, hit_count=10)

    datastore_connection.hit.commit()

    lucene_rule: Analytic = random_model_obj(Analytic)
    lucene_rule.rule = "howler.id:*"
    lucene_rule.rule_type = "lucene"
    lucene_rule.rule_crontab = "0 0 * * *"

    lucene_executor = create_executor(lucene_rule)

    eql_rule: Analytic = random_model_obj(Analytic)
    eql_rule.rule = """
    sequence with maxspan=3000h
        [any where howler.score > 0]
        [any where howler.score > 100]
    """
    eql_rule.rule_type = "eql"
    eql_rule.rule_crontab = "0 0 * * *"

    eql_executor = create_executor(eql_rule)

    sigma_rule: Analytic = random_model_obj(Analytic)
    sigma_rule.rule = textwrap.dedent(
        """
        title: Example Howler Sigma Rule
        id: 811ac553-c775-4dea-a65b-d0d2e6d6bf82
        status: test
        description: A basic example of using sigma rule notation to query howler
        references:
            - https://github.com/SigmaHQ/sigma
        author: You
        date: 2024-01-25
        modified: 2024-01-25
        tags:
            - attack.command_and_control
        logsource:
            category: nbs
        detection:
            selection1:
                howler.status:
                - resolved
                - on-hold
            selection2:
                howler.status:
                - open
                - in-progress
            condition: 1 of selection*
        falsepositives:
            - Unknown
        level: informational
        """
    )
    sigma_rule.rule_type = "sigma"
    sigma_rule.rule_crontab = "0 0 * * *"

    sigma_executor = create_executor(sigma_rule)

    not_a_rule: Analytic = random_model_obj(Analytic)
    not_a_rule.rule = None
    not_a_rule.rule_type = None
    not_a_rule.rule_crontab = None

    # No in-depth testing of results, just making sure basic executors run without errors
    lucene_executor()
    eql_executor()
    sigma_executor()
    create_executor(not_a_rule)()
