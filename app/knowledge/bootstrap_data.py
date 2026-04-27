from __future__ import annotations

from .ontology_store import OntologyStore


def seed_default_ontology(store: OntologyStore) -> None:
    if store.nodes:
        return

    store.upsert_node(
        node_id="comp:STM32F103",
        name="STM32F103 微控制器",
        node_type="Component",
        aliases=["stm32", "mcu", "stm32f103c8t6"],
        attributes={"category": "MCU", "package": "LQFP48", "voltage": "3.3V"},
    )
    store.upsert_node(
        node_id="comp:TPS5430",
        name="TPS5430 降压芯片",
        node_type="Component",
        aliases=["tps5430", "dc-dc", "buck"],
        attributes={"category": "PMIC", "input_voltage": "5V-36V"},
    )
    store.upsert_node(
        node_id="comp:AO3400",
        name="AO3400 MOSFET",
        node_type="Component",
        aliases=["ao3400", "mosfet", "nmos"],
        attributes={"category": "Discrete", "package": "SOT-23"},
    )
    store.upsert_node(
        node_id="pkg:LQFP48",
        name="LQFP48 封装",
        node_type="Package",
        aliases=["lqfp48"],
        attributes={"pins": 48},
    )
    store.upsert_node(
        node_id="std:JEDEC",
        name="JEDEC 标准",
        node_type="Standard",
        aliases=["jedec"],
        attributes={"scope": "package and device naming"},
    )

    store.add_edge(source="comp:STM32F103", target="pkg:LQFP48", relation="has_package")
    store.add_edge(source="comp:STM32F103", target="std:JEDEC", relation="conforms_to")
    store.add_edge(source="comp:TPS5430", target="comp:AO3400", relation="drives")
    store.add_edge(source="comp:TPS5430", target="std:JEDEC", relation="conforms_to")

    store.save()
