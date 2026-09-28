# Author: GPT-6 Astra
# Date: 2026-09-28 15:22
# PURPOSE: Tether v2 wraps one cable around physical posts, resolves continuous
# blade contact and rolling covers, and renders deterministic ARC gameplay.
# SRP/DRY check: Pass â€” inspected rn01, sk04, kb01 and sp01; none supplies flexible
# obstacle wrapping. Local triangle shortening and contact geometry are defined once.
"""A cable-powered rover whose actual route around posts limits its reach."""

from functools import lru_cache
from collections import namedtuple
from itertools import combinations
from math import hypot, isfinite, cos, sin, pi

import numpy as np
from arcengine import ARCBaseGame, Camera, GameState, Level, RenderableUserDisplay

EPS = 1e-9
CELL, OX, OY = 6, 2, 2
WHITE, SILVER, GRAY, DARK, BLACK = 0, 1, 2, 4, 5
RED, BLUE, SKY, YELLOW, ORANGE, GREEN = 8, 9, 10, 11, 12, 14
DIRECTIONS = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}
BODY_RADIUS = .55
GUARD_HALF = .48
LEVELS = [dict(name="The safe side",size=(10,9),dock=(2,4),core=(5,4),
              obstacles=((3.2,3.6,3.8,5.3),),cable=4.2,cutters=()),
          dict(name="Cover before lifting",size=(10,9),dock=(1,7),core=(9,2),
              obstacles=((2.3,5.3,3.3,9.),(4.8,5.5,5.4,7.4),(6.7,2.3,7.7,4.7)),cable=14.,
              cutters=((4.8,3.5,.35),(6.,6.8,.25)),
              guard_start=(7,7),guard_rail=((6,7),(7,7)),guard_target=1),
          dict(name="Turn the cover",size=(10,10),dock=(1,7),core=(9,2),
              obstacles=((2.3,5.3,3.3,10.),(4.8,5.5,5.4,7.4),(6.7,2.3,7.7,4.7)),cable=14.,
              cutters=((4.8,3.5,.35),(6.,6.8,.25)),
              guard_start=(7,8),guard_rail=((7,8),(7,7),(6,7)),guard_target=1)]
State = namedtuple("State", "rover path carrying done dead pulse feedback focus facing guard latched")


def cross(first, second, third):
    return ((second[0]-first[0])*(third[1]-first[1])
            -(second[1]-first[1])*(third[0]-first[0]))


def canonical(points):
    result = []
    for point in points:
        point = tuple(round(value, 9) for value in point)
        if not result or point != result[-1]:
            result.append(point)
    return tuple(result)


def cable_length(path):
    return sum(hypot(second[0]-first[0], second[1]-first[1])
               for first, second in zip(path, path[1:]))


def segment_clear(first, second, obstacles):
    """Clip against each open rectangle interior; boundary contact is allowed."""
    for left, top, right, bottom in obstacles:
        low_time, high_time = 0.0, 1.0
        for origin, delta, low, high in ((first[0], second[0]-first[0], left, right),
                                       (first[1], second[1]-first[1], top, bottom)):
            if abs(delta) < EPS:
                if not low+EPS < origin < high-EPS:
                    low_time, high_time = 1.0, 0.0
                    break
            else:
                entry, leave = sorted(((low+EPS-origin)/delta, (high-EPS-origin)/delta))
                low_time, high_time = max(low_time, entry), min(high_time, leave)
        if low_time < high_time-EPS:
            return False
    return True


def clip_triangle(polygon, triangle):
    """Convex polygon clipping; all accepted points stay inside the old bend."""
    orientation = 1 if cross(*triangle) > 0 else -1
    for first, second in zip(triangle, triangle[1:]+triangle[:1]):
        if not polygon:
            break
        clipped, previous = [], polygon[-1]
        old_side = orientation*cross(first, second, previous)
        for current in polygon:
            new_side = orientation*cross(first, second, current)
            if (old_side >= -EPS) != (new_side >= -EPS):
                fraction = old_side/(old_side-new_side)
                clipped.append((previous[0]+(current[0]-previous[0])*fraction,
                                previous[1]+(current[1]-previous[1])*fraction))
            if new_side >= -EPS:
                clipped.append(current)
            previous, old_side = current, new_side
        polygon = clipped
    return canonical(polygon)


def hull(points):
    ordered = sorted(set(points))
    if len(ordered) < 3:
        return tuple(ordered)
    chains = []
    for ordering in (ordered, list(reversed(ordered))):
        chain = []
        for point in ordering:
            while len(chain) > 1 and cross(chain[-2], chain[-1], point) <= EPS:
                chain.pop()
            chain.append(point)
        chains.append(chain[:-1])
    return tuple(chains[0]+chains[1])


def shorten_bend(first, middle, last, obstacles):
    if abs(cross(first, middle, last)) <= EPS:
        return canonical((first, last))
    triangle, points = (first, middle, last), [first, last]
    for left, top, right, bottom in obstacles:
        polygon = clip_triangle(((left, top), (right, top), (right, bottom), (left, bottom)), triangle)
        area = sum(a[0]*b[1]-a[1]*b[0] for a, b in zip(polygon, polygon[1:]+polygon[:1]))
        if abs(area) > EPS:
            points.extend(polygon)
    boundary = hull(points)
    if len(boundary) <= 2:
        return canonical((first, last))
    start, finish = boundary.index(first), boundary.index(last)
    choices = []
    for direction in (1, -1):
        chain, index = [first], start
        while index != finish:
            index = (index+direction) % len(boundary)
            chain.append(boundary[index])
        choices.append(tuple(chain))
    # The outer hull chain keeps the solids on the same side as the old bend.
    return max(choices, key=lambda chain: sum(abs(cross(first, last, point)) for point in chain))


@lru_cache(maxsize=50000)
def tighten(path, obstacles):
    path = canonical(path)
    while True:
        changed = False
        for index in range(1, len(path)-1):
            old = path[index-1:index+2]
            replacement = shorten_bend(*old, obstacles)
            if replacement == old:
                continue
            old_length, new_length = cable_length(old), cable_length(replacement)
            if new_length > old_length+1e-7:
                raise ValueError("Cable tightening increased the local path length")
            if new_length < old_length-EPS or len(replacement) < len(old):
                path = canonical(path[:index-1]+replacement+path[index+2:])
                changed = True
                break
        if not changed:
            return path


def closest_point(point, first, last):
    dx, dy = last[0]-first[0], last[1]-first[1]
    length_squared = dx*dx+dy*dy
    fraction = 0 if length_squared < EPS else max(0, min(1,
        ((point[0]-first[0])*dx+(point[1]-first[1])*dy)/length_squared))
    return first[0]+fraction*dx, first[1]+fraction*dy


def disc_segment(center, radius, first, last):
    point = closest_point(center, first, last)
    return hypot(center[0]-point[0], center[1]-point[1]) <= radius+EPS


def disc_triangle(center, radius, first, middle, last):
    area = cross(first, middle, last)
    if abs(area) > EPS:
        orientation = 1 if area > 0 else -1
        if all(orientation*cross(start, end, center) >= -EPS
               for start, end in ((first, middle), (middle, last), (last, first))):
            return True
    return any(disc_segment(center, radius, start, end)
               for start, end in ((first, middle), (middle, last), (last, first)))


def position_at(first, last, fraction):
    return (first[0]+(last[0]-first[0])*fraction,
            first[1]+(last[1]-first[1])*fraction)


@lru_cache(maxsize=40000)
def sweep_intervals(path, destination, obstacles):
    """Partition at exact changes of the taut cable's fixed final support.

    For rectangles, a support can change only when the moving endpoint aligns
    with two dock/corner supports. Extra collinearity events are harmless. Between
    events the stationary prefix and one endpoint triangle cover the full sweep,
    including reversal and paths whose full winding overlaps itself.
    """
    supports = {path[0]}
    for left, top, right, bottom in obstacles:
        supports.update(((left, top), (right, top), (right, bottom), (left, bottom)))
    times, start = {0., 1.}, path[-1]
    for first, last in combinations(sorted(supports), 2):
        before, after = cross(first, last, start), cross(first, last, destination)
        if abs(after-before) > EPS:
            time = -before/(after-before)
            if EPS < time < 1-EPS:
                times.add(round(time, 12))
    times, intervals = sorted(times), []
    for low, high in zip(times, times[1:]):
        middle = position_at(start, destination, (low+high)/2)
        taut = tighten(path+(middle,), obstacles)
        prefix = taut[:-1] if len(taut) > 1 else taut
        intervals.append((low, high, prefix))
    return tuple(intervals)


@lru_cache(maxsize=50000)
def cable_sweep_hit(path, destination, obstacles, cutters):
    """Return first (fraction, exact cable contact, cutter index), or None."""
    start = path[-1]
    for low, high, prefix in sweep_intervals(path, destination, obstacles):
        first, last = position_at(start, destination, low), position_at(start, destination, high)
        hits = []
        for number, (cx, cy, radius) in enumerate(cutters):
            center = (cx, cy)
            static_hit = any(disc_segment(center, radius, a, b) for a, b in zip(prefix, prefix[1:]))
            if not static_hit and not disc_triangle(center, radius, prefix[-1], first, last):
                continue
            earliest = low
            if not static_hit and not disc_segment(center, radius, prefix[-1], first):
                left, right = low, high
                for _ in range(36):
                    middle = (left+right)/2
                    point = position_at(start, destination, middle)
                    if disc_triangle(center, radius, prefix[-1], first, point):
                        right = middle
                    else:
                        left = middle
                earliest = right
            contact_path = prefix+(position_at(start, destination, earliest),)
            contact = min((closest_point(center, a, b) for a, b in zip(contact_path, contact_path[1:])),
                          key=lambda point: hypot(cx-point[0], cy-point[1]))
            hits.append((earliest, contact, number))
        if hits:
            return min(hits, key=lambda hit: (hit[0], hit[2]))
    return None


def initial(level):
    return State(level["dock"], (level["dock"],), False, False, False, 0,
                 "ready", level["dock"], (0, -1),level.get("guard_start"),False)


def body_blocker(level, state, destination):
    width, height = level["size"]
    if not (BODY_RADIUS <= destination[0] <= width-BODY_RADIUS
            and BODY_RADIUS <= destination[1] <= height-BODY_RADIUS):
        return destination
    for left, top, right, bottom in level["obstacles"]:
        expanded = ((left-BODY_RADIUS, top-BODY_RADIUS, right+BODY_RADIUS, bottom+BODY_RADIUS),)
        if not segment_clear(state.rover, destination, expanded):
            return (max(left, min(right, destination[0])), max(top, min(bottom, destination[1])))
    return None


def body_cutter_hit(level, start, destination):
    hits = []
    for number, (cx, cy, radius) in enumerate(level["cutters"]):
        if not disc_segment((cx, cy), radius+BODY_RADIUS, start, destination):
            continue
        low, high = 0., 1.
        for _ in range(36):
            middle = (low+high)/2
            if disc_segment((cx, cy), radius+BODY_RADIUS, start, position_at(start, destination, middle)):
                high = middle
            else:
                low = middle
        hits.append((high, (cx, cy), number))
    return min(hits, default=None)


def plan_step(level,state,direction):
    destination=(state.rover[0]+direction[0],state.rover[1]+direction[1])
    guard=state.guard
    if guard is not None and not state.latched and destination==guard:
        next_guard=(guard[0]+direction[0],guard[1]+direction[1])
        rail=level["guard_rail"]
        connected=any((guard==first and next_guard==last) or (guard==last and next_guard==first)
                      for first,last in zip(rail,rail[1:]))
        if not connected or body_blocker(level,state._replace(rover=guard),next_guard) is not None:
            return None,guard,"guard-stop"
        guard=next_guard
    blocker=body_blocker(level,state,destination)
    if blocker is not None:
        return None,blocker,"bumper"
    return destination,guard,None


def exposed_intervals(cutter,guard_start,guard_end):
    """Exact fractions during which a translating square hood exposes the disc."""
    if guard_start is None:
        return ((0.,1.),)
    margin=GUARD_HALF-cutter[2]
    if margin<0:
        return ((0.,1.),)
    low,high=0.,1.
    for dimension in (0,1):
        offset=guard_start[dimension]-cutter[dimension]
        delta=guard_end[dimension]-guard_start[dimension]
        if abs(delta)<EPS:
            if abs(offset)>margin+EPS:
                return ((0.,1.),)
        else:
            first,last=sorted(((-margin-offset)/delta,(margin-offset)/delta))
            low,high=max(low,first),min(high,last)
    if low>high+EPS:
        return ((0.,1.),)
    intervals=[]
    if low>EPS:intervals.append((0.,min(1.,low)))
    if high<1-EPS:intervals.append((max(0.,high),1.))
    return tuple(intervals)


def motion_contact(level,state,destination,guard_destination,body_only=False):
    """First actual exposed-blade contact; hood motion never grants early safety."""
    contacts=[]
    for number,cutter in enumerate(level["cutters"]):
        for low,high in exposed_intervals(cutter,state.guard,guard_destination):
            start=position_at(state.rover,destination,low)
            finish=position_at(state.rover,destination,high)
            one=dict(cutters=(cutter,))
            body=body_cutter_hit(one,start,finish)
            possibilities=[(body,"blade")]
            if not body_only:
                path=tighten(state.path+(start,),level["obstacles"])
                possibilities.append((cable_sweep_hit(path,finish,level["obstacles"],(cutter,)),"cut"))
            for contact,kind in possibilities:
                if contact is None:continue
                fraction=low+(high-low)*contact[0]
                # At the closing boundary the entire blade is already enclosed.
                if high<1-EPS and fraction>=high-EPS:continue
                contacts.append((fraction,contact[1],number,kind))
    return min(contacts,key=lambda item:(item[0],item[3],item[2]),default=None)


def move(level, state, direction):
    destination,guard,refusal=plan_step(level,state,direction)
    if refusal is not None:
        return state._replace(feedback=refusal,focus=guard,facing=direction)
    path = tighten(state.path+(destination,), level["obstacles"])
    if cable_length(path) > level["cable"]+EPS:
        return state._replace(feedback="taut", focus=path[-2] if len(path)>1 else state.rover, facing=direction)
    contact=motion_contact(level,state,destination,guard)
    if contact is not None:
        fraction,focus,number,kind=contact
        stopped = position_at(state.rover, destination, fraction)
        path = tighten(state.path+(stopped,), level["obstacles"])
        stopped_guard=position_at(state.guard,guard,fraction) if guard is not None else None
        return state._replace(rover=stopped,path=path,guard=stopped_guard,dead=True,feedback=kind,focus=focus,facing=direction)
    latched=state.latched or (guard is not None and not exposed_intervals(
        level["cutters"][level["guard_target"]],guard,guard))
    feedback="latch" if latched and not state.latched else "push" if guard!=state.guard else "move"
    return state._replace(rover=destination,path=path,guard=guard,latched=latched,feedback=feedback,focus=destination,
                          facing=direction, done=state.carrying and destination == level["dock"])


def reel_direction(level, state):
    if len(state.path) < 2:
        return None
    target, length = state.path[-2], cable_length(state.path)
    choices = []
    for action, direction in DIRECTIONS.items():
        toward = ((target[0]-state.rover[0])*direction[0]+(target[1]-state.rover[1])*direction[1])
        destination,guard,refusal=plan_step(level,state,direction)
        if toward <= EPS or refusal is not None:
            continue
        path = tighten(state.path+(destination,), level["obstacles"])
        if cable_length(path) < length-EPS:
            choices.append((cable_length(path), action, direction))
    if choices:
        return min(choices, key=lambda option: (option[0], option[1]))[2]
    return None


def reel(level, state):
    direction = reel_direction(level, state)
    if direction is not None:
        selected = move(level, state, direction)
        return selected if selected.dead else selected._replace(feedback="reel")
    target = state.path[-2] if len(state.path)>1 else level["dock"]
    return state._replace(feedback="reel-stop", focus=target)


def transition(level, state, action, point=None):
    if state.done or state.dead:
        return state
    state = state._replace(pulse=1-state.pulse)
    if action in DIRECTIONS:
        return move(level, state, DIRECTIONS[action])
    if action == 5:
        return reel(level, state)
    if action == 6:
        core = level["core"]
        if point is None or hypot(point[0]-core[0], point[1]-core[1]) > .7:
            return state._replace(feedback="miss", focus=state.rover if point is None else point)
        if state.carrying:
            return state._replace(feedback="loaded", focus=state.rover)
        if (hypot(state.rover[0]-core[0], state.rover[1]-core[1]) > 1.05
                or not segment_clear(state.rover, core, level["obstacles"])):
            return state._replace(feedback="far", focus=core)
        return state._replace(carrying=True, feedback="pickup", focus=state.rover)
    return state._replace(feedback="refused", focus=state.rover)


def pixel(point):
    return OX+CELL*point[0], OY+CELL*point[1]


def rect(frame, left, top, width, height, color):
    x1, y1 = max(0, round(left)), max(0, round(top))
    x2, y2 = min(64, round(left+width)), min(64, round(top+height))
    if x1 < x2 and y1 < y2:
        frame[y1:y2, x1:x2] = color


def line(frame, first, second, color):
    count = max(1, round(hypot(second[0]-first[0], second[1]-first[1])*2))
    for fraction in np.linspace(0, 1, count+1):
        point = position_at(first, second, fraction)
        rect(frame, *point, 1, 1, color)


def disc(frame, center, radius, color):
    for dy in range(-int(radius)-1, int(radius)+2):
        for dx in range(-int(radius)-1, int(radius)+2):
            if hypot(dx, dy) <= radius:
                rect(frame, center[0]+dx, center[1]+dy, 1, 1, color)


def battery(frame, center, small=False):
    x, y = center
    if small:
        rect(frame, x-1, y-1, 3, 3, BLUE)
        rect(frame, x, y, 1, 1, SKY)
        return
    rect(frame, x-2, y-2, 5, 5, BLUE)
    rect(frame, x-1, y-2, 2, 5, SKY)
    line(frame, (x-2, y-3), (x+2, y-3), SILVER)
    line(frame, (x-2, y+3), (x+2, y+3), DARK)
    rect(frame, x, y-4, 1, 1, WHITE)


def draw_rover(frame, position, facing, carrying, dead, pulse):
    sprite = np.array([
        [-1,-1,GRAY,WHITE,GRAY,-1,-1],
        [BLACK,GREEN,SKY,SKY,SKY,GREEN,BLACK],
        [BLACK,GRAY,SKY,SKY,SKY,GRAY,BLACK],
        [-1,GREEN,GRAY,GRAY,GRAY,GREEN,-1],
        [BLACK,GREEN,DARK,DARK,DARK,GREEN,BLACK],
        [BLACK,GREEN,GRAY,GRAY,GRAY,GREEN,BLACK],
        [-1,-1,GRAY,ORANGE,GRAY,-1,-1]], dtype=int)
    if dead:
        sprite[sprite == SKY] = DARK
        sprite[sprite == WHITE] = GRAY
        sprite[sprite == GREEN] = GRAY
    elif pulse:
        sprite[1, 0] = sprite[5, 6] = GRAY
    if carrying:
        sprite[4:6, 2:5] = BLUE
        sprite[4, 3] = SKY
    turns = {(0,-1):0, (1,0):-1, (0,1):2, (-1,0):1}[facing]
    sprite = np.rot90(sprite, turns)
    cx, cy = pixel(position)
    for row, values in enumerate(sprite):
        for column, color in enumerate(values):
            if color >= 0:
                rect(frame, cx+column-3, cy+row-3, 1, 1, color)


class TetherDisplay(RenderableUserDisplay):
    def __init__(self, game):
        self.game = game

    def render_interface(self, frame):
        game, state, level = self.game, self.game.st, self.game.lvl
        animation = game.animation
        before = animation["before"] if animation else state
        fraction = min(1, animation["index"]/8) if animation else 1
        rover = position_at(before.rover, state.rover, fraction)
        guard = position_at(before.guard,state.guard,fraction) if state.guard is not None else None
        path = tighten(before.path+(rover,), level["obstacles"]) if animation else state.path
        cut = state.dead and fraction >= 1
        frame[:, :] = DARK
        width,height=level["size"]
        rect(frame, OX-3, OY-3, width*CELL+6, height*CELL+6, GRAY)
        rect(frame, OX-1, OY-1, width*CELL+2, height*CELL+2, SILVER)
        for row in range(1,height):
            for column in range(1,width):
                x, y = pixel((column, row))
                rect(frame, x, y, 1, 1, GRAY)
        for left, top, right, bottom in level["obstacles"]:
            x, y = pixel((left, top))
            width, height = (right-left)*CELL, (bottom-top)*CELL
            rect(frame, x+2, y+2, width, height, GRAY)
            rect(frame, x, y, width, height, DARK)
            rect(frame, x, y, width-2, height-2, GRAY)
            line(frame, (x, y), (x+width-2, y), WHITE)
            line(frame, (x, y), (x, y+height-2), SILVER)
        dock_x, dock_y = pixel(level["dock"])
        rect(frame, dock_x-4, dock_y-4, 9, 9, DARK)
        rect(frame, dock_x-3, dock_y-3, 7, 8, GRAY)
        line(frame, (dock_x-4, dock_y-4), (dock_x-4, dock_y+4), WHITE)
        line(frame, (dock_x+4, dock_y-4), (dock_x+4, dock_y+4), WHITE)
        line(frame, (dock_x-4, dock_y+4), (dock_x+4, dock_y+4), BLUE)
        rect(frame, dock_x-1, dock_y+4, 3, 1, GREEN if state.done else SKY)
        spool = (dock_x,dock_y+8) if dock_x<12 else (dock_x-8,dock_y)
        disc(frame, spool, 4, BLACK)
        disc(frame, spool, 3, GRAY)
        remaining = max(0, level["cable"]-cable_length(path))/level["cable"]
        for number in range(round(32*remaining)):
            angle, radius = (number % 16)*pi/8, 3 if number<16 else 1.6
            rect(frame, spool[0]+radius*cos(angle), spool[1]+radius*sin(angle), 1, 1, ORANGE)
        rect(frame, spool[0], spool[1], 1, 1, WHITE)
        line(frame,(spool[0],spool[1]-3) if dock_x<12 else (spool[0]+3,spool[1]),(dock_x,dock_y),ORANGE)
        if guard is not None:
            rail=list(map(pixel,level["guard_rail"]))
            for first,last in zip(rail,rail[1:]):
                horizontal=first[1]==last[1]
                for offset in (-3,3):
                    delta=(0,offset) if horizontal else (offset,0)
                    line(frame,(first[0]+delta[0],first[1]+delta[1]),
                         (last[0]+delta[0],last[1]+delta[1]),GRAY)
            for endpoint in (rail[0],rail[-1]):
                rect(frame,endpoint[0]-1,endpoint[1]-1,3,3,DARK)
        for cx,cy,radius in level["cutters"]:
            x,y=pixel((cx,cy))
            disc(frame,(x,y),radius*CELL+1,BLACK)
            disc(frame,(x,y),radius*CELL-.6,GRAY)
            for number in range(8):
                angle=number*pi/4+(fraction*pi/4 if animation else 0)
                endpoint=(x+radius*CELL*cos(angle),y+radius*CELL*sin(angle))
                rect(frame,*endpoint,1,1,WHITE)
            rect(frame,x,y,1,1,RED)
        if guard is not None:
            x,y=pixel(guard)
            closed=state.latched and fraction>=1
            rect(frame,x-3,y-3,7,7,GRAY if closed else BLACK)
            rect(frame,x-2,y-2,5,5,SILVER)
            line(frame,(x-2,y-2),(x+2,y-2),WHITE)
            line(frame,(x-1,y),(x+2,y),GRAY)
            line(frame,(x-1,y+2),(x+2,y+2),GRAY)
            if closed:
                rect(frame,x-3,y,1,2,GREEN)
            else:
                rect(frame,x-3,y-1,1,3,BLACK)
                rect(frame,x+3,y-1,1,3,BLACK)
        for first, second in zip(path, path[1:]):
            first, second = pixel(first), pixel(second)
            count = max(1, round(hypot(second[0]-first[0], second[1]-first[1])*2))
            for amount in np.linspace(0, 1, count+1):
                point = position_at(first, second, amount)
                focus = pixel(state.focus)
                if not cut or state.feedback != "cut" or hypot(point[0]-focus[0], point[1]-focus[1]) > 2:
                    rect(frame, *point, 1, 1, ORANGE)
        pickup = animation and state.feedback == "pickup"
        if not state.carrying:
            battery(frame, pixel(level["core"]))
        draw_rover(frame, rover, state.facing, state.carrying and not pickup, cut, state.pulse)
        if pickup:
            battery(frame, position_at(pixel(level["core"]), pixel(rover), fraction), small=fraction>.7)
        if cut:
            x, y = pixel(state.focus)
            for dx, dy in ((-3,0),(3,0),(0,-3),(0,3)):
                rect(frame, x+dx, y+dy, 1, 1, YELLOW if state.pulse else RED)
        elif state.feedback not in ("ready", "move", "reel", "pickup","push","latch"):
            x, y = pixel(state.focus)
            radius = 2+state.pulse
            color = YELLOW if state.feedback == "undo" else RED
            line(frame, (x-radius,y-radius), (x+radius,y-radius), color)
            line(frame, (x-radius,y+radius), (x+radius,y+radius), color)
        return frame


class Te01(ARCBaseGame):
    def __init__(self):
        self.lvl, self.st = LEVELS[0], initial(LEVELS[0])
        self.animation, self.history = None, []
        self.display = TetherDisplay(self)
        levels = [Level(sprites=[], grid_size=(64,64), data={}, name=level["name"]) for level in LEVELS]
        super().__init__("te01", levels, Camera(0,0,64,64,DARK,DARK,[self.display]),
                         False, len(levels), [1,2,3,4,5,6,7])

    def on_set_level(self, level):
        self.lvl = LEVELS[self.level_index]
        self.st, self.animation, self.history = initial(self.lvl), None, []

    def handle_reset(self):
        if self._state in (GameState.NOT_PLAYED, GameState.WIN):
            self.full_reset()
        else:
            self.level_reset()

    def finish_action(self):
        self.animation = None
        if self.st.dead:
            self.lose()
        elif self.st.done:
            self.next_level()
        self.complete_action()

    def step(self):
        if self.action.id.value == 0:
            self.complete_action()
            return
        if self.animation is not None:
            self.animation["index"] += 1
            if self.animation["index"] >= 9:
                self.finish_action()
            return
        before, action = self.st, self.action.id.value
        if action == 7:
            if self.history:
                self.st = self.history.pop()._replace(feedback="undo", pulse=1-before.pulse)
                self.st = self.st._replace(focus=self.st.rover)
            else:
                self.st = before._replace(feedback="undo-empty", focus=before.rover, pulse=1-before.pulse)
        else:
            point = None
            if action == 6:
                data = self.action.data or {}
                x, y = data.get("x"), data.get("y")
                if all(isinstance(value,(int,float)) and isfinite(value) for value in (x,y)) and 0<=x<64 and 0<=y<64:
                    point = ((x-OX)/CELL, (y-OY)/CELL)
            self.history.append(before)
            self.st = transition(self.lvl, before, action, point)
        if self.st.rover != before.rover or self.st.feedback == "pickup":
            self.animation = {"before":before, "index":0}
            return
        self.finish_action()


