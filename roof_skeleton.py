# ##### BEGIN GPL LICENSE BLOCK #####
#
#  House - Toit par squelette droit (chantier S2, builder)
#  Copyright (C) 2025 mvaertan
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
# ##### END GPL LICENSE BLOCK #####

"""TOIT SQUELETTE — le toit DÉDUIT du plan (roof_type 'SKELETON').

Consomme plan2d (contour unifié maison+ailes) et skeleton (pans
exacts) pour construire, sur N'IMPORTE QUELLE emprise rectiligne:
- une DALLE prismatique par pièce de pan (coplanaires par arête),
- les FAÎTIÈRES sur les arcs horizontaux, les ARÊTIERS (coins
  convexes) en tuiles de rive, les NOUES (coins rentrants) en zinc,
- les TUILES par pan (mêmes pas et pose que la couverture GABLE,
  prédicat point-dans-pan), les fascias et gouttières sur TOUS les
  égouts.

Le L/T/U n'est plus un cas particulier: c'est le même algorithme que
le rectangle. Contrainte v1 (règle de construction affichée): murs de
même arase partout → plain-pied (les ailes plus basses gardent le
moteur historique).
"""

import math
import random

import bpy
import bmesh
from mathutils import Euler, Matrix, Vector

from . import norms, plan2d, skeleton
from .features import (TILE_L, TILE_OVERLAP, TILE_W, _add_box,
                       _create_tile_master, _new_mesh_obj,
                       _simple_material, _tile_accessory_material,
                       detail_level)
from .norms import TOIT_DALLE_RAMPANT_EP as ROOF_T


def _corner_convex(contour, v, eps=1e-6):
    """Le sommet v du contour CCW est-il convexe (arêtier) ou rentrant
    (noue)?"""
    n = len(contour)
    for i in range(n):
        if abs(contour[i][0] - v[0]) < eps and abs(contour[i][1] - v[1]) < eps:
            ax, ay = contour[i - 1]
            bx, by = contour[i]
            cx, cy = contour[(i + 1) % n]
            cross = (bx - ax) * (cy - by) - (by - ay) * (cx - bx)
            return cross > 0
    return True   # pas un sommet du contour (arc interne)


def _point_in_convex(p, poly, eps=1e-6):
    n = len(poly)
    sign = 0
    for i in range(n):
        ax, ay = poly[i][:2]
        bx, by = poly[(i + 1) % n][:2]
        cr = (bx - ax) * (p[1] - ay) - (by - ay) * (p[0] - ax)
        if abs(cr) < eps:
            continue
        s = 1 if cr > 0 else -1
        if sign == 0:
            sign = s
        elif s != sign:
            return False
    # sign == 0 → polygone dégénéré (aplati): jamais "dedans" — les
    # pièces-lamelles le long des arêtiers validaient des tuiles
    # entières qui débordaient le pan (crénelage vu au rendu)
    return sign != 0


def build(props, collection, contour, wall_top, pitch_deg, tile_color):
    """Construit le toit complet sur `contour` (CCW), égouts à
    `wall_top`. Retourne la liste des objets créés."""
    slope = math.tan(math.radians(pitch_deg))
    cosp = math.cos(math.radians(pitch_deg))
    sinp = math.sin(math.radians(pitch_deg))
    o_eave = max(0.0, props.roof_overhang)
    cells = skeleton.faces(contour)
    n = len(contour)
    edges = [(contour[i], contour[(i + 1) % n]) for i in range(n)]
    objs = []

    def z_of(d):
        return wall_top + d * slope

    # --- DALLES: un prisme par pièce (épaisseur verticale) ---
    bm = bmesh.new()
    for _i, pieces in cells:
        for piece in pieces:
            top = [bm.verts.new((x, y, z_of(d))) for (x, y, d) in piece]
            bot = [bm.verts.new((x, y, z_of(d) - ROOF_T))
                   for (x, y, d) in piece]
            bm.faces.new(top)
            bm.faces.new(list(reversed(bot)))
            m = len(top)
            for k in range(m):
                k2 = (k + 1) % m
                bm.faces.new([top[k], top[k2], bot[k2], bot[k]])
    slab_mat = _simple_material("House_Roof_Slab", (0.35, 0.30, 0.28),
                                roughness=0.9)
    objs.append(_new_mesh_obj("Roof_Skeleton", bm, collection, "roof",
                              slab_mat))

    # --- ARCS: faîtières / arêtiers / noues ---
    tile_mat = _tile_accessory_material(tile_color)
    zinc = _simple_material("House_Zinc", (0.62, 0.65, 0.67),
                            roughness=0.35, metallic=0.9)
    bm_f = bmesh.new()   # faîtières + arêtiers (terre cuite)
    bm_n = bmesh.new()   # noues (zinc)

    def _bar(bm_t, p0, p1, radius, lift):
        axis = p1 - p0
        if axis.length < 0.08:
            return
        quat = axis.normalized().to_track_quat('Z', 'Y')
        seg = bmesh.ops.create_cone(bm_t, cap_ends=True, segments=10,
                                    radius1=radius, radius2=radius,
                                    depth=axis.length)
        c = (p0 + p1) / 2 + Vector((0, 0, lift))
        bmesh.ops.transform(bm_t, verts=seg['verts'],
                            matrix=Matrix.Translation(c)
                            @ quat.to_matrix().to_4x4())

    for a, b, _i, _j in skeleton.ridge_segments(cells):
        pa = Vector((a[0], a[1], z_of(a[2])))
        pb = Vector((b[0], b[1], z_of(b[2])))
        if abs(a[2] - b[2]) < 1e-6:            # FAÎTAGE horizontal
            _bar(bm_f, pa, pb, norms.FAITIERE_RAYON, 0.03)
        else:                                   # incliné: arêtier/noue
            low = a if a[2] < b[2] else b
            if _corner_convex(contour, (low[0], low[1])):
                _bar(bm_f, pa, pb, norms.TUILE_RIVE_RAYON, 0.06)
            else:
                # NOUE: bande zinc plaquée
                axis = pb - pa
                quat = axis.normalized().to_track_quat('Z', 'Y')
                seg = bmesh.ops.create_cube(bm_n, size=1.0)
                bmesh.ops.transform(
                    bm_n, verts=seg['verts'],
                    matrix=Matrix.Diagonal((norms.ZINC_NOUE_LARGEUR,
                                            0.012, axis.length, 1.0)))
                bmesh.ops.transform(
                    bm_n, verts=seg['verts'],
                    matrix=Matrix.Translation((pa + pb) / 2
                                              + Vector((0, 0, 0.02)))
                    @ quat.to_matrix().to_4x4())
    if len(bm_f.verts):
        objs.append(_new_mesh_obj("Roof_Hips", bm_f, collection, "roof",
                                  tile_mat))
    else:
        bm_f.free()
    if len(bm_n.verts):
        objs.append(_new_mesh_obj("Roof_Valleys", bm_n, collection,
                                  "roof", zinc))
    else:
        bm_n.free()

    # --- FASCIAS + GOUTTIÈRES sur tous les égouts ---
    bm = bmesh.new()
    bm_g = bmesh.new()
    for (x0, y0), (x1, y1) in edges:
        d = Vector((x1 - x0, y1 - y0, 0))
        L = d.length
        if L < 0.05:
            continue
        u = d / L
        # normale extérieure (contour CCW → extérieur à droite)
        nrm = Vector((u.y, -u.x, 0))
        # bandeau
        c = (Vector((x0, y0, 0)) + Vector((x1, y1, 0))) / 2 \
            + nrm * (o_eave + norms.FASCIA_EP / 2)
        quat = u.to_track_quat('X', 'Z')
        seg = bmesh.ops.create_cube(bm, size=1.0)
        ze = wall_top - o_eave * slope
        bmesh.ops.transform(bm, verts=seg['verts'],
                            matrix=Matrix.Diagonal(
                                (L, norms.FASCIA_EP, norms.FASCIA_H, 1.0)))
        bmesh.ops.transform(bm, verts=seg['verts'],
                            matrix=Matrix.Translation(
                                c + Vector((0, 0, ze - ROOF_T + 0.06
                                            - norms.FASCIA_H / 2)))
                            @ quat.to_matrix().to_4x4())
        if getattr(props, 'include_gutters', False):
            segg = bmesh.ops.create_cone(
                bm_g, cap_ends=True, segments=12,
                radius1=norms.GOUTTIERE_RAYON,
                radius2=norms.GOUTTIERE_RAYON, depth=L)
            gq = u.to_track_quat('Z', 'Y')
            bmesh.ops.transform(
                bm_g, verts=segg['verts'],
                matrix=Matrix.Translation(
                    c + nrm * 0.04
                    + Vector((0, 0, ze - ROOF_T + 0.02)))
                @ gq.to_matrix().to_4x4())
    fascia_mat = _simple_material("House_Fascia", (0.92, 0.92, 0.90),
                                  roughness=0.5)
    objs.append(_new_mesh_obj("Roof_Fascia", bm, collection, "roof",
                              fascia_mat))
    if len(bm_g.verts):
        gut_mat = _simple_material("House_Gutter", (0.75, 0.76, 0.78),
                                   roughness=0.35, metallic=0.8)
        objs.append(_new_mesh_obj("Gutters", bm_g, collection, "gutter",
                                  gut_mat))
    else:
        bm_g.free()

    # --- TUILES par pan (si couverture) ---
    if props.roof_covering != 'TILES':
        return objs
    # ✅ S5: arcs (arêtiers/noues/faîtages) adjacents à chaque pan —
    # les plans de COUPE verticaux des tuiles de bord
    arcs_by_pan = {}
    for a, b, i2, j2 in skeleton.ridge_segments(cells):
        for k in (i2, j2):
            arcs_by_pan.setdefault(k, []).append((a, b))
    random.seed(norms.derive_seed(props, 'tuiles_squelette'))
    step_v = TILE_L - TILE_OVERLAP
    delta = math.atan2(norms.TUILE_NEZ_H, step_v)
    positions = []
    cut_tiles = []   # ✅ S5: (pos, rot, pan, arcs) des tuiles de bord
    for i, pieces in cells:
        (ex0, ey0), (ex1, ey1) = edges[i]
        ed = Vector((ex1 - ex0, ey1 - ey0, 0))
        eL = ed.length
        if eL < 0.05:
            continue
        u = ed / eL
        nrm_in = Vector((-u.y, u.x, 0))           # intérieur (CCW)
        dir_v = nrm_in * cosp + Vector((0, 0, 1)) * sinp
        normal = u.cross(dir_v)
        if normal.z < 0:
            normal = -normal
        base_r = Matrix((
            (u.x, dir_v.x, normal.x),
            (u.y, dir_v.y, normal.y),
            (u.z, dir_v.z, normal.z))) @ Matrix.Rotation(0, 3, 'X')
        base_rot = (Matrix.Rotation(-delta, 3, u)
                    @ base_r).to_euler()
        dmax = max(pt[2] for p in pieces for pt in p)
        # ✅ bornes en u du PAN (pas de l'égout): aux coins convexes le
        # pan s'élargit au-delà de son égout (éventail du coin) — la
        # grille de pose doit couvrir toute l'étendue des pièces
        u0 = min((pt[0] - ex0) * u.x + (pt[1] - ey0) * u.y
                 for p in pieces for pt in p)
        u1 = max((pt[0] - ex0) * u.x + (pt[1] - ey0) * u.y
                 for p in pieces for pt in p)
        n_u = int((u1 - u0 + 2 * o_eave) / TILE_W) + 1
        origin = (Vector((ex0, ey0, wall_top + 0.02))
                  + u * (u0 - o_eave) - nrm_in * (o_eave * 1.0)
                  + Vector((0, 0, -o_eave * slope)))
        slope_len = (dmax + o_eave) / cosp
        pan_arcs = arcs_by_pan.get(i, [])

        def _in_pan(q):
            if any(_point_in_convex(q, piece) for piece in pieces):
                return True
            t_along = (q[0] - ex0) * u.x + (q[1] - ey0) * u.y
            t_out = (q[0] - ex0) * nrm_in.x + (q[1] - ey0) * nrm_in.y
            return (-o_eave - 0.05 < t_out < 0.02
                    and -o_eave - 0.05 < t_along < eL + o_eave + 0.05)

        iv = 0
        while iv * step_v + TILE_L <= slope_len + 0.03 + 1e-6:
            for iu in range(n_u):
                p = origin + u * (iu * TILE_W) + dir_v * (iv * step_v) \
                    + normal * 0.008
                # ✅ S5: les 4 COINS de l'emprise de la tuile décident:
                # tout dedans → instance; partiel → tuile COUPÉE réelle
                # au plan de l'arc (fini le crénelage sous les noues)
                corners = []
                for cu in (0.02, TILE_W - 0.02):
                    for cv in (0.02, TILE_L - 0.02):
                        corners.append((p.x + u.x * cu
                                        + nrm_in.x * cosp * cv,
                                        p.y + u.y * cu
                                        + nrm_in.y * cosp * cv))
                ins = [_in_pan(c) for c in corners]
                if not any(ins):
                    continue
                j = math.radians(0.8)
                r = Euler((base_rot.x + random.uniform(-j, j),
                           base_rot.y + random.uniform(-j, j),
                           base_rot.z + random.uniform(-j, j)), 'XYZ')
                pos = p + normal * random.uniform(0, 0.003)
                if all(ins):
                    positions.append((pos, r))
                else:
                    cut_tiles.append((pos, r, i, pan_arcs))
            iv += 1

    if positions:
        master = None
        for o in collection.objects:
            if o.name.startswith("Tile_Master"):
                master = o
                break
        if master is None:
            master = _create_tile_master(collection, tile_color)
        mesh = bpy.data.meshes.new("Roof_Tiles_Points")
        mesh.from_pydata([tuple(p) for p, _r in positions], [], [])
        mesh.update()
        attr = mesh.attributes.new("tile_rot", 'FLOAT_VECTOR', 'POINT')
        flat = []
        for _p, r in positions:
            flat.extend((r.x, r.y, r.z))
        attr.data.foreach_set('vector', flat)
        obj = bpy.data.objects.new("Roof_Tiles", mesh)
        obj["house_part"] = "roof"
        collection.objects.link(obj)
        ng = bpy.data.node_groups.new("House_SkelTile_Instancer",
                                      'GeometryNodeTree')
        ng.interface.new_socket("Geometry", in_out='INPUT',
                                socket_type='NodeSocketGeometry')
        ng.interface.new_socket("Geometry", in_out='OUTPUT',
                                socket_type='NodeSocketGeometry')
        n_in = ng.nodes.new('NodeGroupInput')
        n_pts = ng.nodes.new('GeometryNodeMeshToPoints')
        n_pts.mode = 'VERTICES'
        n_obj = ng.nodes.new('GeometryNodeObjectInfo')
        n_obj.transform_space = 'ORIGINAL'
        n_obj.inputs['Object'].default_value = master
        if 'As Instance' in n_obj.inputs:
            n_obj.inputs['As Instance'].default_value = True
        n_attr = ng.nodes.new('GeometryNodeInputNamedAttribute')
        n_attr.data_type = 'FLOAT_VECTOR'
        n_attr.inputs['Name'].default_value = "tile_rot"
        n_inst = ng.nodes.new('GeometryNodeInstanceOnPoints')
        n_out = ng.nodes.new('NodeGroupOutput')
        ng.links.new(n_in.outputs['Geometry'], n_pts.inputs['Mesh'])
        ng.links.new(n_pts.outputs['Points'], n_inst.inputs['Points'])
        ng.links.new(n_obj.outputs['Geometry'], n_inst.inputs['Instance'])
        ng.links.new(n_attr.outputs['Attribute'], n_inst.inputs['Rotation'])
        ng.links.new(n_inst.outputs['Instances'], n_out.inputs['Geometry'])
        mod = obj.modifiers.new("TileInstancer", 'NODES')
        mod.node_group = ng
        objs.append(obj)

    # ✅ S5: TUILES COUPÉES réelles le long des arêtiers/noues — chaque
    # tuile de bord est une copie du master, posée puis BISECTÉE par
    # les plans verticaux des arcs de son pan (côté égout conservé).
    if cut_tiles:
        master = next((o for o in collection.objects
                       if o.name.startswith("Tile_Master")), None)
        bm_c = bmesh.new()
        kept = 0
        for pos, rot, pan_i, pan_arcs in cut_tiles:
            (ex0, ey0), (ex1, ey1) = edges[pan_i]
            ed = Vector((ex1 - ex0, ey1 - ey0, 0))
            eave_mid = Vector((ex0, ey0, 0)) + ed / 2
            tb = bmesh.new()
            tb.from_mesh(master.data)
            M = (Matrix.Translation(pos)
                 @ rot.to_matrix().to_4x4())
            bmesh.ops.transform(tb, verts=tb.verts, matrix=M)
            for a, b in pan_arcs:
                av = Vector((a[0], a[1], 0))
                bv = Vector((b[0], b[1], 0))
                d2 = (bv - av)
                if d2.length < 1e-6:
                    continue
                # ✅ ne couper que par les arcs À PORTÉE de la tuile:
                # le PLAN infini d'une noue prolongée tranchait des
                # tuiles à l'autre bout du même pan (bande de dalle
                # nue le long des arêtiers — vu au rendu)
                pc2 = Vector((pos.x, pos.y, 0))
                tseg = max(0.0, min(1.0, (pc2 - av).dot(d2)
                                    / d2.length_squared))
                if (pc2 - (av + d2 * tseg)).length > 0.75:
                    continue
                n2 = Vector((-d2.y, d2.x, 0)).normalized()
                s = 1.0 if n2.dot(eave_mid - av) >= 0 else -1.0
                # retirer le côté OPPOSÉ à l'égout du pan
                res = bmesh.ops.bisect_plane(
                    tb, geom=tb.verts[:] + tb.edges[:] + tb.faces[:],
                    plane_co=av, plane_no=-s * n2,
                    clear_outer=True, clear_inner=False)
                cut_edges = [e for e in res['geom_cut']
                             if isinstance(e, bmesh.types.BMEdge)]
                if cut_edges:
                    try:
                        bmesh.ops.holes_fill(tb, edges=cut_edges)
                    except Exception:
                        pass
                if not tb.faces:
                    break
            if tb.faces:
                kept += 1
                tb.verts.index_update()   # indices AVANT le mapping
                vmap = {}
                for vv in tb.verts:
                    vmap[vv.index] = bm_c.verts.new(vv.co)
                for ff in tb.faces:
                    try:
                        bm_c.faces.new([vmap[vv.index] for vv in ff.verts])
                    except ValueError:
                        pass
            tb.free()
        if len(bm_c.faces):
            try:
                from . import look
                cmat = look.tile_material(
                    tile_color, getattr(props, 'roof_finish', 'AUTO'))
            except Exception:
                cmat = _tile_accessory_material(tile_color)
            oc = _new_mesh_obj("Roof_Tiles_Cut", bm_c, collection,
                               "roof", cmat)
            for poly in oc.data.polygons:
                poly.use_smooth = True
            objs.append(oc)
        else:
            bm_c.free()
        print(f"[House] ✓ Toit squelette: {len(positions)} tuiles "
              f"instanciées + {kept} tuiles COUPÉES sur {len(cells)} pans")
    else:
        print(f"[House] ✓ Toit squelette: {len(positions)} tuiles sur "
              f"{len(cells)} pans")
    return objs
