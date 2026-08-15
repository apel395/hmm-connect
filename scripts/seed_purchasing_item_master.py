#!/usr/bin/env python3
"""Seed all historical Purchasing PO item names directly into Item Master.

No Excel input is required. The 943 high-confidence names are reused from
seed_purchasing_tax_profiles.MAPPING_B64; the remaining 482 names are embedded
below. Existing products are matched by normalized name and keep their current
code/group/UOM/conversion. Missing products are created with deterministic PIM-
codes and a conservative PURCHASING/IMPORTED PO ITEM placeholder classification.

Dry-run by default. Use --apply to commit.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
import zlib
from collections import Counter
from decimal import Decimal

from app.core.database import SessionLocal
from app.models.item_group import ItemGroup
from app.models.item_subgroup import ItemSubgroup
from app.models.product import Product
from scripts.seed_purchasing_tax_profiles import MAPPING_B64

REMAINDER_B85 = """c-q~a|85&clE+`AVBioL8;2D2!*cRZYKE<0b7s0HJw2wFy~AM?F*a8gC6MCcjKjUhzR$kcRnJhrEJM!1%KAG55`~eX_|w(h)z#JY<FEhwLSN4=Ui|ptb^kxe*{CW#)1G{0$B~Zt#rH3Y<>l4oYIa7x{vV3#>)E@@<wyAqr`~Ec`ERFwskBo=`7h(k#qaa8+2XgE{5Z1{`Iej2tILJ_tEn&Q-s)<$n*TmOuUB(Aoqbqe&~NMW^%bob*XwgS|4`rl^z!=hqQ0K5=wrQjNAkOi7ytMDEi7wCy3|x<Y!c$q>1X3CX3G!t`MO?EJzomsay5V73m-4$3*nV-ysL#)p#C;n2;bFg@o~1S-^(wY$=_GY%d_?QPx9^Mhc*3uw!9h8@AdihdU;<0PYuX#*@zO(tl7R1(e4|{v{!Bmhjy&}7K|!Y85c~x;w>0Vu8ne>HLK3MEgH~ZzfXC#bpxXPBTBMzi^g@>--d}YL(X*0PaR0=MCFD56hBu(UFG*j5Unpx*R-0wtCziV0T9&n_4>WwUDelgJzHMXD=}?W^+(}3ZT{oNqB)zN&Q9yqdA<1QKKOkD>1rmwdwKqlJfT=uphj5>M~8!FT_exS_)EoGqHV%Rw!*9m1GzIk{<0l|a<MK!w?N4`jd{Y|(|$MPv`cByW&Ezvr*d>YxvqiPy~-*xu2Rfh8F4hF*t+MiNyhcNpwDilcv>&RA9+4I4KfZ&?ehFG=(KuuEo=)qU7z2oI=cK2l;1<PR5@*^$f}a|_WG1KR3VmHZbz>vLFYpkU<xb2NiY&}xr~e`(U~@10s467q?Z?$XY=cN^+5An&#vpMz}>*Un|}~>B|nl~(+gXu?zLOyk&W;Z6$S0Tp^MqYX?@-3rlnx6!p^)7|Fh4Gtf;)+wvj3Cl_NHy-auEC9&5@)^6VIxu;7d-5;NI%?gYN$uY5J?CVr_hQI8|w1v1fNWkC5VQP|Nlx|E-vE?1&-#}<{)BrNu~S0yx{HgRPVWW=mFXuGF^8u(HTxu9GWX^tu5m|oFtzuyO?<4A3z@%U(5G-A1|ZOiDCNmA84t05jK=cetvfbIu-e5|NsA@wwXy_N>Q2&Kvyl|7g1@40;>_YwC82TzOg+d;mSi&!FNY)ONDpNbgNn24R#B^yv{F|Jak!vow`uDA+%r?8Wua`=Qa<|*hp90sSwgpT^SKF<e;q)q8z_ss@%!`KC>wkIPl;>31j;wvLp7sq<L%<iGewVbB0g4VU4Qc`NHgJm_G=^N0filR(WQsv#D?FeknJ|3}X4yBA&+y&&aGG<Dio!uJsA;ZhMHzU~=&xltpQ6}u=Dy28b7Rn=3u>zc!0T!GW`l!?#DbJ<N=-@T*-0Qroa{8Hef$#A5AmJII<!G~PN>p$GyK5RkWWdU$N|7H;bA=p!qasaBs8xc__a!&%w}dq9IkSiB&pvj_#3MR(T9p)wJX5*l#Fg(BE$|u;<Z_hjEPVzie7Rn&gH>6-r!%oR=ZnVPoUNDhRRFoJ7gx1>73(sXpYPTm>R$WtLp@*IdpQz2)I4OYw5N#6RKZSsAdGFCde)$>?t~rZG~}Xkbnqo}{f|z0QZMTZI=@`3))!%lpMHONVvbw7T#Xrws;H=mc?o$JyQr`ApKu<aVurY|a4yQlp^1IKwIv^*{(KM&b2_rW(qG6|zA8|moem){sfLxRcT74~LK%;=QEB-qtOL~bDr-Ov@bDIl3s^z}1|J<2ic54pU>hx|GA0(=lH!nIy!)&v?SB#}@_S%I2^?#5$A`Ws3oe@l*#XEVU8Eb79TMml5;VU#X~VdQ+B<^va(teZ1_#Ina$pusKNKyMa%RQy9DIL(E#lANhI<IOl(ElJ<AawoQYC{<{YZ=^BYO&ZqDOk@Z15o2X4|92OFqOzrPRk2<yyhQ;j$%iJI@Q$>{Bi3TUK84en!0;?~D<11eVtZ-@1?*&l%-xbh$a`_uk;Xn(NYLxI%5=Xh7P;pceg@<y=hK`3B5xxQ{0%w@a%`dtlCL$iy*+J&#=dW6UG9U17Up&Ph%KuR{UPeOP@JFva}TDNjSqGCF~-z4CclR9kAyu98I{2UwL+YCWf@oKw+dJf%$WTh#?d(3{9u8-E)td5C+X-*A?y`C}0QE17KTZPsKE<{ACGJD?rMB~#3KQMs3x+^HP3p|rNQIa#L@Z9<vW0j@&*EbyCyPVkmhDi>;e*pVJ{g-;0VI^SS6wsu!A6FK~cj86;vn0HI)6*izgQA0A7Z~Two+Q_p3pYMi{@OMtj`6UMc4rhTHNs_Y8*dVh}<Ge4d(J3mX@iv@2PL(R9ag|4w<PswKD9$^9+`4uJd2j@bTvQn+-79LHvQuJ`sEiG)PAw_LRZ!FF**wz!?wP+qr-(g&IjIJJ7{R;poKE6)B%3j87~j{6-_}ck?48Z8!_Uv@dVW@)-wkZJzF4msC-FryAo<w*?%!szte!%ry|25m{`&`@Vw*<}S9PeNHS!lMUeg>Z5x`R6L&7sQPg*-6SHnzMl$v}^>1F4Tv55<IsF{NI38_>Gw^6jT(^!zOV$HSt`octiE~3+gPH9ske*Y`WQb0Y%-i)mYCXvA%9&OdwLOsZ)HsrChzbeG{{Y|{l=xs^754-+-leZRe1WlN66iSr#_pm9ekk1|26KKj@H|9f>wy|)O9>+8|I2pX|1a;LdYBTMgq(9FL>!7*|>ula4vdDD;6q&Os<jyXqCbHpnj}iIZWCJ=D6HKMpjL6TT8^nS$l}C)eEDJS+_3Pe86nUB<V}n+a?vazP;JatS&hV@7RilD>6|&k`HV~|z!&gG*zSxWlff2dhVycHmO({}rXdk#>SE^H;QOO1Bp3#M9NjYyc>RY`obJX%JEgOxr=bYjSyFft`s}7tT*7EtA#P6Lpt1bH>xEpBquz&KVe{#^zb5v(=6Cfz&MpD9t4mF5A<gdsvIT+xEWIO;xcHUKH8cOj!_v`hy^gOpi+N!jzbfUcGDwIrwz5g|clP(}4*O`6DNQ0v{u$E!QL*AGUU+8T6ts&b3`74#&pGw)Z`9ock4P7Nx_EzcCPev8u{CHblUo+cAv4-wLplb^IAug-lYSS3*drUjIPWfeLK(XuMd=9waIK{2Sdq=$AIpTwk5a*#9gf*H}7THOYUyEw?e1f`vL?__9!;1VE7p_U5MlOk#vsel?C1Zb}-9uDHm+F#H;Yu&}nbLF9G3%@S@=&%`t~jH3gz7U3c*u0dtAr`74D6NshB3E(q?}B()v>}x1+I;oiz0}5lXTK4PU?kie%q808oPDN0Kd^b;KX$wJ;DqX%Q7*gJA&IohSi~$Jcni+xYyNtkl2jPUZ-JBdwty6W4X>OwyCd;a$?VM=`=ne?Y_Zn9q|b$JZH({iqlZK4|n&pq!aeabpVle_?L=bwj~h{8@1Gn{PPL7kZW6gzLpDIJzom;ay5V73m-4$3mJiY<6SNMP4@6Yh_7agkD-~J{KDC7TF_6AZh!Q9eSR%>$a^w*Vu+cd&3FF1f&Ph86f}tL$a3m}wrfc{xDXDZ&4$OM!4U6;WE0M;=?v&bX>XO1ZU+|BM|Y+HUNMJUzfIQr09dg1Fn=C&K%^zh2kZx>4XE`N8gQb=%E&QMDv_xot26LJ?xd;KxDP$`C-hb&%5x-kZ=2T-95LROz`O<S1SBOk8;Vqq+2ydnVV&**R~5}|<}Do|?<DI)&F?h*7&IF$GW8O_cfdXBn}!D+qxOy`k#f`SVBZNExd%pWe`P0T7BpQ*8bQ`tRq5FcX)ri|XPk;O?SyuYoig!AcGE#%?!6)VYbU^4-VUJxi`InrD5jiC)Lt^TgtxUugZn5gyF%N8XAQLkfs1(?ktGdP)8{f}2YO5yWncvu&?tm!g7Q_~$$dY|DAp!sc*@o#)eXvKccY_bDjsQc$RcCZG6j}>sfUVUdwi@m4X!{*v!S;WLnHoGWx*5Cqd4QT)Nwa>d)Ty2C2TAWc46(~8^pHh9s%E$Y$yhNyQ@GMr?5rJ8#LM8NhpX^%7;SxDzm__y%x2H3|jE<F^Q$_-4qotl?{Un7h4^gESIRE>xI~CM$SZCM3&tU7E(E)q0O=>a-e$48QDoj2f#*Ai`fNf25&ZU_sJVX;98pnJB3RoXA5k;S?JFIT+FWEX@zQx70NJ0TI8o*B`Tw&cs1DD?|*-g=fJ>CDhx1R=|g>2H*6$}%IS2;^p=gzGEKmJqYLE~Y1I0Fg=z}WQqCzGG0@ta*T%WlbGB67pl*)Eu0e}ZMcrIl7HtSp3xNrsh&E=YshlVwMGlyF02<4*W5b3d;_%29k61LSQii+&b+Z>0y361Wkjhb*|JT5Q9>2&;hhP-1@&Z(Y{_+YRu_>0`0Ma4wWWx*6aiU3^V2U<A4pd1xbu1PrsjSdr9hyj^#vMDA1Q(1Axg4PH`A!2j>2Nk@ZBTcMSiN#=J2`1^YqQ=!qB90WY&tr2svMy*PGd`(`e}s*&crDB*xwv6!GmxDeb79h?Fwk8q>9a%RFqd<KOHCdN1K+G^}F@I(z3KER=4<Ahw5{)#rl2dJinYTew)h=o3eDhL4PoK2rOrLD72Aj+TkdENxORouovI^v>o7#HpL(J_WS6l$c1$tAd)OnSWGLY=@&Z|e^bQJEjk3f+1Q5gw_Inb9Q|3RaDV9ck@wSQnLB{o3Ayfehp|}!IqD^T!`j?X#A1Q%Yq;SIi5EdpdDj8VE^MStc>XSOS&L6lJ0R6Y+3$o^AcpinE>&Gv3%yPquP#(L*ar^W-XP|o+;4|Cfid-s3b>z&hwQKl{kJ$|ZDdtR|NI9H4pF-e-m-2A-~96*dwpQmF^531jLnc<_vuI4>!YHU481}t*+F(1S}Qm@*hO}zeL@Ng8jmKbC{#(_8XY4SS}hfq)@+hp@oSlsYG{LP)fUo^?b}c!6S?kpDTkG&-F@6m)c~d(hZ+IE;q;F=k#*{QSl|SJ$DHs&ZL1l<Z>XDUOI=`upYvN#<jPg0GDDkEp33Qzl|H3NHF4R{T@;^y24;4V^2j}Z?pF#O02@=XsXR?kpU~2r;t+lBwHT=TM@P6j|5H*}P+MV_1a1JMDl}9sL+f%6`(je4Scg~r8~4LcxbBBS4{b)Jv6DR9oRpJ)D1-XGUo`#dM^^Nwv!T>Y8;nm!-yi(vi*7M@6ZyOEpphHe!E0bwdXr9&u<@`dxGiF-^1|7+P&llK(k4B?OS3!TbjBjHQKB+*K5P?8FzvC;H!jjht|HwaO~s;uoq8RoQ!>^oR6xfQ$|_f(+RIhSLsa2aCe@{fh0Am@@=X&0*kk1$Brv1=p{PA<Z|LY~A9|W^A#oW){i-4qNyXkVpJ0Zfgs=|R2e5h8112piF?rZg<k$>50f{~Hf;!ZkhemS10k;9ODSdIQRW>Z4%ML$=JphMIt>=`Qp4+=e;H<%qrK(V9s?>iVp!p9c->p~ckUv+yr?dIu-F(ptiFUK~a=r>+*Y)D6maiA5O~c7|>koCW{rI7tFXUHFXQ%b*yve*XPcy&y($f9b$eu?Pja31g^?whLcDy~VUIKG&ig)#>tYiwYW!kd#IzS5iHhjlNKkqh?0kqRNX<nl9b_6%Xi0(|4EjO*%_JIpHwX_|<geHt~y6MMM7NCskxM|2dAk?6G;M!7cd9FN!E3tt_#7&<Rz$)VjYI8NQ)Pn&GTy<Osg^!0U*Y^z90t%Fki3ZD8VaJ+p2<7hto)8sqr06b4N}>AV9${jql6?;MM_AalG+?Noi(6vR+axp^Fk@VG-Vn-ME7Wt_<}~G;{D^f1>vi{`1ysp-!O%ew-a0Q*q*O&5fg(Cv=$H+I<58LEJY+I_S9XFFxt85$QRS}PHR<+{fh%E+N0mwGtu{KmUmW3vxi+*zHL|F9at%jy1XX2~Qlb-0AqEaL>aE2r88ztbj!*97c?5b9YTDgsWH#t<*0x)a=tb73g!+U*ckpDSWpl`3q7qbl_W>du!i7To*Z%`w(gi&"""

GROUP_CODE = "9"
GROUP_NAME = "PURCHASING"
SUBGROUP_CODE = "9-1"
SUBGROUP_NAME = "IMPORTED PO ITEM"
DEFAULT_UOM = "Pcs"

EXEMPT_REFERENCE = "PP 49 Tahun 2022"
STANDARD_REFERENCE = "PMK 131 Tahun 2024"
REVIEW_REFERENCE = "Finance review required"


def normalized(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "", (value or "").upper())


def load_rows() -> list[dict]:
    high_mapping = json.loads(zlib.decompress(base64.b64decode(MAPPING_B64)).decode("utf-8"))
    rows = [
        {
            "Item": name,
            "Proposed Tax Category": category,
            "Confidence": "HIGH",
            "Reason": "High-confidence classification from historical Purchasing tax mapping",
        }
        for name, category in high_mapping.items()
    ]
    remainder = json.loads(
        zlib.decompress(base64.b85decode(REMAINDER_B85.encode("ascii"))).decode("utf-8")
    )
    rows.extend(remainder)
    by_key = {}
    for row in rows:
        key = normalized(str(row.get("Item") or ""))
        if key and key not in by_key:
            by_key[key] = row
    result = list(by_key.values())
    if len(result) != 1425:
        raise RuntimeError(
            f"Embedded Purchasing item payload expected 1425 unique items, got {len(result)}"
        )
    return result


def ensure_group(db):
    group = db.query(ItemGroup).filter(ItemGroup.code == GROUP_CODE).first()
    if group is None:
        group = ItemGroup(code=GROUP_CODE, name=GROUP_NAME, is_active=True)
        db.add(group)
        db.flush()
    else:
        group.name = GROUP_NAME
        group.is_active = True

    subgroup = db.query(ItemSubgroup).filter(ItemSubgroup.code == SUBGROUP_CODE).first()
    if subgroup is None:
        subgroup = ItemSubgroup(
            code=SUBGROUP_CODE,
            name=SUBGROUP_NAME,
            group_id=group.id,
            is_active=True,
        )
        db.add(subgroup)
    else:
        subgroup.name = SUBGROUP_NAME
        subgroup.group_id = group.id
        subgroup.is_active = True
    db.flush()


def tax_profile(row: dict) -> tuple[str, bool, Decimal, str]:
    category = str(row.get("Proposed Tax Category") or "REVIEW_REQUIRED").upper()
    confidence = str(row.get("Confidence") or "").upper()
    if confidence == "HIGH" and category == "EXEMPT":
        return "EXEMPT", False, Decimal("0"), EXEMPT_REFERENCE
    if confidence == "HIGH" and category == "STANDARD":
        return "STANDARD", True, Decimal("11.0000"), STANDARD_REFERENCE
    return "REVIEW_REQUIRED", False, Decimal("0"), REVIEW_REFERENCE


def make_code(name: str, occupied: set[str]) -> str:
    digest = hashlib.sha1(normalized(name).encode("utf-8")).hexdigest().upper()
    for width in range(10, 17):
        candidate = f"PIM-{digest[:width]}"[:20]
        if candidate not in occupied:
            occupied.add(candidate)
            return candidate
    raise RuntimeError(f"Unable to allocate product code for {name}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed all 1,425 historical Purchasing item names into Item Master"
    )
    parser.add_argument("--apply", action="store_true", help="Commit changes")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        ensure_group(db)
        rows = load_rows()
        products = db.query(Product).order_by(Product.id).all()
        occupied = {str(p.code or "").upper() for p in products}

        by_name: dict[str, Product] = {}
        duplicate_existing: set[str] = set()
        for product in products:
            key = normalized(product.name)
            if not key:
                continue
            if key in by_name:
                duplicate_existing.add(key)
            else:
                by_name[key] = product

        stats = Counter()
        for row in rows:
            name = str(row["Item"]).strip()
            key = normalized(name)
            if key in duplicate_existing:
                stats["skipped_duplicate_existing_name"] += 1
                continue

            category, taxable, rate, reference = tax_profile(row)
            reason = str(row.get("Reason") or "")[:255]
            product = by_name.get(key)

            if product is None:
                product = Product(
                    code=make_code(name, occupied),
                    name=name,
                    group_code=GROUP_CODE,
                    group_name=GROUP_NAME,
                    subgroup_code=SUBGROUP_CODE,
                    subgroup_name=SUBGROUP_NAME,
                    uom=DEFAULT_UOM,
                    usage_uom=DEFAULT_UOM,
                    conversion=Decimal("1"),
                    description="Imported from historical Purchasing PO descriptions",
                    cost_price=Decimal("0"),
                    selling_price=Decimal("0"),
                    tax_category=category,
                    is_taxable=taxable,
                    tax_rate=rate,
                    tax_reason=reason,
                    tax_reference=reference,
                    minimum_stock=Decimal("0"),
                    reorder_level=Decimal("0"),
                    maximum_stock=Decimal("0"),
                    lead_time_days=0,
                    is_active=True,
                )
                db.add(product)
                db.flush()
                by_name[key] = product
                stats["created"] += 1
                stats[f"created_{category.lower()}"] += 1
                continue

            changed = False
            if category != "REVIEW_REQUIRED":
                desired = {
                    "tax_category": category,
                    "is_taxable": taxable,
                    "tax_rate": rate,
                    "tax_reason": reason,
                    "tax_reference": reference,
                }
                for field, value in desired.items():
                    if getattr(product, field) != value:
                        setattr(product, field, value)
                        changed = True
            if not product.is_active:
                product.is_active = True
                changed = True

            stats["updated" if changed else "unchanged"] += 1
            stats[f"matched_{category.lower()}"] += 1

        print("Purchasing Item Master seed summary:")
        print("  source_unique_items=1425")
        for key in sorted(stats):
            print(f"  {key}={stats[key]}")

        if args.apply:
            db.commit()
            print("Seed committed successfully.")
        else:
            db.rollback()
            print("Dry-run complete; transaction rolled back. Re-run with --apply to commit.")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
