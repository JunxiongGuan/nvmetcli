PKGNAME = nvmetcli
MANPAGE = ${PKGNAME}.8
HTMLFILE = ${PKGNAME}.html
XMLFILE = ${PKGNAME}.xml
INSTALL ?= install
PREFIX := /usr

ASCIIDOC = asciidoc
XMLTO = xmlto --skip-validation

DOCDATA = ${XMLFILE} ${HTMLFILE}
 
${MANPAGE}: ${DOCDATA}
	${XMLTO} man $<
 
%.xml: %.txt
	${ASCIIDOC} -b docbook -d manpage -o $@ $<
 
%.html: %.txt
	${ASCIIDOC} -a toc -o $@ $<
 
installdoc: man8

man8:
	${INSTALL} -m 644 ${MANPAGE} ${PREFIX}/share/man/man8

uninstalldoc:
	-rm -f ${PREFIX}/share/man/man8/${MANPAGE}

clean:
	-rm -f ${MANPAGE} ${HTMLFILE} ${XMLFILE}
