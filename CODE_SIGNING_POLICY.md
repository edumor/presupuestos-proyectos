# Code signing policy / Política de firma de código

Free code signing for Windows is provided by [SignPath.io](https://about.signpath.io/), certificate by
[SignPath Foundation](https://signpath.org/).
*(Pendiente de aprobación: hasta entonces el instalador se publica sin firmar.)*

La firma de código gratuita para Windows la provee SignPath.io, con certificado de SignPath Foundation.

## Qué se firma

Solo los binarios compilados a partir del código fuente de este repositorio por el flujo automático
[`.github/workflows/release.yml`](.github/workflows/release.yml) en GitHub Actions: el ejecutable
`PresupuestosApp.exe` y el instalador `Presupuestos-Setup-<versión>.exe`. Los componentes de terceros
no se firman con este certificado.

## Equipo y roles

| Rol | Personas |
| --- | --- |
| Autores (committers) | [Eduardo José Moreno](https://github.com/edumor) |
| Revisores | Eduardo José Moreno: revisa todo cambio de colaboradores externos (pull requests) |
| Aprobadores | Eduardo José Moreno: aprueba manualmente cada pedido de firma de una versión |

Todos los miembros usan autenticación de dos factores en GitHub y en SignPath.

## Privacidad

Este programa no transfiere información a ningún otro sistema conectado a la red, salvo que el
usuario lo pida expresamente (botones "Traer del BCRA" y "Actualizar desde el BCRA", que solo
consultan cotizaciones e inflación publicadas por el Banco Central, sin enviar datos). Todos los datos se guardan en la computadora del usuario
(`%LOCALAPPDATA%\PresupuestosApp`). El programa incluye desinstalador y desinstalarlo no borra los datos.

This program will not transfer any information to other networked systems unless specifically
requested by the user. All data is stored locally on the user's computer.

## Verificación

Windows puede mostrar un aviso las primeras veces que se descarga una versión nueva, hasta que el
archivo gana reputación. Para verificar la firma: clic derecho en el instalador → Propiedades →
Firmas digitales. El firmante debe ser **SignPath Foundation**. Cada Release publica además la
huella SHA-256 del instalador.
