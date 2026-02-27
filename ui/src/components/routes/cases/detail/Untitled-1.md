<h3>Actions</h3>

<ul class="actions_list">

<li>

</li>

<li>

</li>

</ul>

<h3>Data</h3>

<table class="table_overview">

<tbody>

<tr>

<td style="padding:8px;font-weight:bold;">Tangent</td>

<td style="padding:8px;">Triangle</td>

</tr>

<tr>

<td style="padding:8px;font-weight:bold;">Start date</td>

<td style="padding:8px;">1</td>

</tr>

<tr>

<td style="padding:8px;font-weight:bold;">End date</td>

<td style="padding:8px;">1</td>

</tr>

<tr>

<td style="padding:8px;font-weight:bold;">Country</td>

<td style="padding:8px;"><span style="text-transform: uppercase;">Canada</span> / <span style="text-transform: capitalize;">Canada / <span style="text-transform: capitalize;">Canada</span></td>

</tr>

</tbody>

</table>

<h3>Visualization</h3>

```mermaid

graph LR

A[Password Spraying IP] -- Login Failure Account A --> D{ Entra ID }

A[Password Spraying IP] -- Login Failure Account B --> D{ Entra ID }

A[Password Spraying IP] -- Login Failure Account C --> D{ Entra ID }

A[Password Spraying IP] -- Login Failure Account D --> D{ Entra ID }

A[Password Spraying IP] -- Login Failure Account E --> D{ Entra ID }

A[Password Spraying IP] -- Login Failure Account E --> D{ Entra ID }

A[Password Spraying IP] == Login Attempt Account E ==> D{ Entra ID }

D{ Entra ID } ==  Entra ID Returns Code {{error.code}} ==> A

classDef orange fill:#f96,stroke:#333,stroke-width:2px

classDef blue fill:#32bedd,stroke:#333,stroke-width:2px

class D blue

class A orange

```

<style>

/* Actions */

.actions_list li {

display:inline!important;

margin-right: 45px!important;

margin-bottom: 15px!important;

}

.actions_list {

list-style: none!important;

margin: 0px!important;

padding: 0px!important;

}

.actions_list img {

height:20px!important;

margin-bottom:-7px!important;

padding-right:5px!important;

}

/* Tables */

.MuiPaper-root.MuiPaper-elevation.MuiPaper-rounded.MuiPaper-elevation1.MuiTableContainer-root {

box-shadow:unset !important;

width: fit-content !important;

}

/* General */

h3 {

border-bottom: 2px solid #2d7dc9;

/*border-bottom: 5px solid rgba(255, 255, 255, 0.12);*/

/*color: #393939;*/

}

/* Visualization */

.mermaid {

background-color:#fff;

padding:15px;

text-align: center;

}

/* Boites */

.actor.actor-top {

stroke: #393939 !important;

fill: lightgrey !important;

}

/* Tête du bonhomme */

.actor-man circle {

stroke: #393939 !important;

fill: #28A745 !important;

}

/* Corps du bonhomme */

.actor-man line {

stroke: #393939 !important;

fill: #393939 !important;

}

/* Lignes verticales */

.actor-line {

stroke: #393939 !important;

fill: #393939 !important;

}

/* Description des flèches horizontales */

.messageText {

fill: #393939 !important;

stroke: none;

}

/* Têtes de flèches */

marker#arrowhead path {

fill: #DC3545 !important;

}

/* Texte en-dessous du bonhomme */

text.actor > tspan {

fill: #393939 !important;

}

/* Flèches horizontales */

.messageLine0, .messageLine1 {

stroke-width: 1.5;

stroke-dasharray: none;

stroke: #393939 !important;

}

/* Texte dans boites */

.actor-box {

font-weight: bold !important;

color: #393939 !important;

}

/* Cacher le bonhomme du bas */

.actor-bottom {

display:None;

}

</style>
