# Author: GPT-6 Astra
# Date: 2026-09-28 15:31
# PURPOSE: Lockkeeper's passing-berth slice uses a planar canal graph, two
# blocking boats, exact conserved water and a fully visible angled scene.
# SRP/DRY check: Pass — one immutable transition owns all rules and tests.

from collections import namedtuple
from fractions import Fraction
from math import isfinite

import numpy as np
from arcengine import ARCBaseGame,Camera,GameState,Level,RenderableUserDisplay

WHITE,STONE,GRAY,MID,DARK,BLACK=0,1,2,3,4,5
RED,WATER,SKY,YELLOW,WOOD,GREEN=8,9,10,11,12,14
LEVELS=(
    dict(name='Raise the boat',tutorial=True,heights=(0,0,6),infinite=((0,0),(2,6)),
         gates=((0,1),(1,2)),valves=((0,1),(1,2)),boats=(1,),goals=(2,),
         opened=0,selected=0,covered=()),
    dict(name='One lock',tutorial=True,heights=(0,0,6),infinite=((0,0),(2,6)),
         gates=((0,1),(1,2)),valves=((0,1),(1,2)),boats=(0,),goals=(2,),
         opened=1,selected=0,covered=()),
    dict(name='Pass the waiting boat',tutorial=False,heights=(0,6,2,6,2,11),infinite=((0,0),),
         gates=((0,1),(1,2),(2,3),(2,4)),
         valves=((0,1),(1,2),(2,3),(2,4),(3,5)),
         boats=(2,3),goals=(3,0),opened=8,selected=0,covered=(2,4)),
)
State=namedtuple('State','heights gates valves boats selected failed won')


def water_row(height):
    return round(58-2*float(height))


def initial(level):
    data=LEVELS[level]
    return State(tuple(map(Fraction,data['heights'])),data['opened'],0,
                 data['boats'],data['selected'],'',False)


def equalize(level,state):
    data=LEVELS[level]
    edges=[pair for index,pair in enumerate(data['gates']) if state.gates>>index&1]
    edges += [pair for index,pair in enumerate(data['valves']) if state.valves>>index&1]
    pending=set(range(len(state.heights)))
    heights=list(state.heights)
    while pending:
        component={pending.pop()}
        changed=True
        while changed:
            changed=False
            for first,second in edges:
                if (first in component)!=(second in component):
                    component.update((first,second));changed=True
        pending-=component
        fixed={Fraction(height) for basin,height in data['infinite'] if basin in component}
        if len(fixed)>1:
            return None
        height=next(iter(fixed)) if fixed else sum(heights[basin] for basin in component)/len(component)
        for basin in component:
            heights[basin]=height
    return state._replace(heights=tuple(heights))


def assess(level,state):
    data=LEVELS[level]
    boats=list(state.boats)
    for index,basin in enumerate(boats):
        if basin<0:
            continue
        row=water_row(state.heights[basin])
        if basin==data['goals'][index] and (index==1 or row<=water_row(6)):
            boats[index]=-1
        elif basin in data['covered']:
            low,high=(1,3) if index==0 else (4,6)
            if row>water_row(low):
                return state._replace(failed='bed')
            if row<water_row(high):
                return state._replace(failed='roof')
    won=all(basin<0 for basin in boats)
    selected=state.selected
    if boats[selected]<0 and not won:
        selected=next(index for index,basin in enumerate(boats) if basin>=0)
    state=state._replace(boats=tuple(boats),selected=selected,won=won)
    if not data['tutorial'] and not won and boats[0]>=0 and min(map(water_row,state.heights[1:]))>water_row(6):
        return state._replace(failed='reserve')
    return state


def water_action(level,state,command):
    """Preview one connection change without mutating its input or losing water."""
    kind,index=command
    data=LEVELS[level]
    if kind=='gate' and 0<=index<len(data['gates']):
        first,second=data['gates'][index]
        if not state.gates>>index&1 and water_row(state.heights[first])!=water_row(state.heights[second]):
            return state
        after=state._replace(gates=state.gates^(1<<index))
    elif kind=='valve' and 0<=index<len(data['valves']):
        after=state._replace(valves=state.valves^(1<<index))
    else:
        return state
    settled=equalize(level,after)
    return state if settled is None else assess(level,settled)


def transition(level,state,command):
    if state.failed or state.won:
        return state
    data=LEVELS[level]
    kind,index=command[:2] if len(command)>=2 else ('invalid',-1)
    after=state
    if kind=='select' and 0<=index<len(state.boats) and state.boats[index]>=0:
        return state._replace(selected=index)
    if kind in ('gate','valve'):
        checked=water_action(level,state,(kind,index))
        return state if checked.failed in ('roof','bed') else checked
    elif kind=='sail' and index not in state.boats:
        origin=state.boats[state.selected]
        gate=next((gate for gate,pair in enumerate(data['gates']) if set(pair)=={origin,index}),None)
        if gate is None or not state.gates>>gate&1:
            return state
        boats=list(state.boats);boats[state.selected]=index
        after=state._replace(boats=tuple(boats))
    else:
        return state
    settled=equalize(level,after)
    if settled is None:
        return state
    checked=assess(level,settled)
    return state if data['tutorial'] and checked.failed else checked


def center(level,basin):
    return (10+21*basin,0) if LEVELS[level]['tutorial'] else ((5,0),(19,0),(33,0),(47,0),(30,-24),(60,0))[basin]


def gate_point(level,index):
    return (20+22*index,14) if LEVELS[level]['tutorial'] else ((12,32),(26,32),(40,32),(22,21))[index]


def valve_point(level,index):
    return (20+22*index,61) if LEVELS[level]['tutorial'] else ((12,61),(26,61),(40,61),(40,38),(55,61))[index]


def controls(level,state):
    data=LEVELS[level]
    output=[(('gate',index),gate_point(level,index)) for index in range(len(data['gates']))]
    output += [(('valve',index),valve_point(level,index)) for index in range(len(data['valves']))]
    for index,basin in enumerate(state.boats):
        if basin>=0 and index!=state.selected:
            x,offset=center(level,basin)
            output.append((('select',index),(x,water_row(state.heights[basin])+offset-2)))
    origin=state.boats[state.selected]
    for first,second in data['gates']:
        basin=second if first==origin else first if second==origin else -1
        if basin>=0 and basin not in state.boats:
            x,offset=center(level,basin)
            output.append((('sail',basin),(x,water_row(state.heights[basin])+offset-2)))
    return output


def rect(frame,x,y,width,height,color):
    left,top=max(0,round(x)),max(0,round(y))
    right,bottom=min(64,round(x+width)),min(64,round(y+height))
    if left<right and top<bottom:
        frame[top:bottom,left:right]=color


def line(frame,first,second,color):
    count=max(abs(round(second[0]-first[0])),abs(round(second[1]-first[1])),1)
    for step in range(count+1):
        rect(frame,first[0]+(second[0]-first[0])*step/count,
             first[1]+(second[1]-first[1])*step/count,1,1,color)


def polygon(frame,points,color):
    for row in range(max(0,min(y for _,y in points)),min(64,max(y for _,y in points)+1)):
        crosses=[]
        for (first_x,first_y),(next_x,next_y) in zip(points,points[1:]+points[:1]):
            if min(first_y,next_y)<=row<max(first_y,next_y):
                crosses.append(first_x+(next_x-first_x)*(row-first_y)/(next_y-first_y))
        if len(crosses)>=2:
            rect(frame,min(crosses),row,max(crosses)-min(crosses)+1,1,color)


def boat_parts(x,y,kind,ghost=False):
    x,y=round(x),round(y)
    ink=WHITE if ghost else DARK
    if kind==0:
        parts=[(x-6,y-2,13,2,ink),(x-5,y,11,1,ink),(x-4,y+1,9,1,ink),
               (x-4,y-5,4,3,ink),(x+1,y-9,1,7,ink),(x+2,y-9,3,2,WHITE if ghost else GREEN)]
        if not ghost:
            parts += [(x-5,y-1,11,1,WHITE),(x-4,y,9,1,WHITE),
                      (x-3,y-4,2,2,WHITE),(x-2,y-4,1,1,SKY)]
    else:
        parts=[(x-6,y-1,13,7,ink),(x-5,y+6,11,2,ink),(x-5,y-3,4,2,ink)]
        if not ghost:
            parts += [(x-5,y,11,2,WHITE),(x-5,y+2,11,4,GRAY),
                      (x-4,y+6,9,1,GRAY),(x-4,y-3,2,2,WHITE),(x-3,y-3,1,1,SKY)]
        parts += [(x+1,y-3,2,2,WHITE if ghost else WOOD),(x+4,y-3,2,2,WHITE if ghost else WOOD)]
    return parts


def boat(frame,x,y,kind,ghost=False):
    for part in boat_parts(x,y,kind,ghost):
        rect(frame,*part)


def contains(x,y,kind,click_x,click_y,ghost=False):
    return any(left<=click_x<left+width and top<=click_y<top+height
               for left,top,width,height,_ in boat_parts(x,y,kind,ghost))


def command_at(level,state,x,y):
    if not all(isinstance(value,(int,float)) and isfinite(value) for value in (x,y)):
        return ('invalid',)
    targets=controls(level,state)
    # Boats are painted above hardware margins. Their visible pixels must win
    # hit testing too; every lever/wheel center remains outside a boat silhouette.
    for index,basin in enumerate(state.boats):
        if basin>=0:
            boat_x,offset=center(level,basin)
            if contains(boat_x,water_row(state.heights[basin])+offset,index,x,y):
                return ('select',index)
    for command,_ in targets:
        if command[0]=='sail':
            after=transition(level,state,command)
            basin=command[1]
            boat_x,offset=center(level,basin)
            if after!=state and not after.failed and contains(
                    boat_x,water_row(state.heights[basin])+offset,state.selected,x,y,True):
                return command
    for command,(target_x,target_y) in targets:
        if command[0] in ('gate','valve') and abs(x-target_x)<=2 and abs(y-target_y)<=2:
            return command
    nearby=[(abs(x-target_x)+abs(y-target_y),command) for command,(target_x,target_y) in targets
            if abs(x-target_x)<=3 and abs(y-target_y)<=3]
    return min(nearby)[1] if nearby else ('invalid',)


def basin(frame,level,index,height):
    x,offset=center(level,index)
    tutorial=LEVELS[level]['tutorial']
    width=18 if tutorial else 6 if index==5 else 12
    depth=8 if not tutorial and index==5 else 4
    bottom=63+offset
    top=16 if tutorial else 10 if index==4 else 20 if index==5 else 34
    left=x-width//2
    rect(frame,left-1,top,width+2,bottom-top,GRAY)
    rect(frame,left,top+1,width,bottom-top-1,WHITE)
    row=water_row(height)+offset
    rect(frame,left,row,width,bottom-row,WATER)
    polygon(frame,[(left,row),(left+width-1,row),(left+width-2,row-depth),(left-1,row-depth)],SKY)
    line(frame,(left,row),(left+width-1,row),WHITE)


class LockDisplay(RenderableUserDisplay):
    def __init__(self,game):
        self.game=game

    def render_interface(self,frame):
        game,state=self.game,self.game.st
        level,data=game.level_index,LEVELS[game.level_index]
        tutorial=data['tutorial']
        frame[:,:]=STONE
        shown=list(map(float,state.heights))
        amount=0
        if game.animation is not None:
            amount=min(1,game.animation['frame']/10)
            shown=[float(old)+(float(new)-float(old))*amount
                   for old,new in zip(state.heights,game.animation['after'].heights)]
        if not tutorial:
            # A real branch between two banks; parked boats leave the main lane.
            branch_end=water_row(shown[4])-24+2
            junction_end=water_row(shown[2])-3
            polygon(frame,[(25,branch_end),(35,branch_end),(39,junction_end),(27,junction_end)],WATER)
            line(frame,(24,branch_end),(26,junction_end),DARK)
            line(frame,(36,branch_end),(40,junction_end),DARK)
        order=range(3) if tutorial else (4,5,0,1,2,3)
        for index in order:
            basin(frame,level,index,shown[index])
        if not tutorial:
            # The front opening of the berth remains visible above the junction.
            polygon(frame,[(26,34),(35,34),(37,42),(28,42)],WATER)
            line(frame,(25,34),(27,42),DARK)
            line(frame,(36,34),(38,42),DARK)
        for index,(first,second) in enumerate(data['gates']):
            lever_x,lever_y=gate_point(level,index)
            opened=state.gates>>index&1
            if not tutorial and index==3:
                line(frame,(lever_x,lever_y+2),(25,34),DARK)
                if opened:
                    rect(frame,24,28,2,7,WOOD)
                else:
                    line(frame,(26,36),(36,38),WOOD)
                    line(frame,(26,37),(36,39),WOOD)
            else:
                first_x,_=center(level,first)
                second_x,_=center(level,second)
                door_x=round((first_x+second_x)/2)
                if opened:
                    row=water_row(shown[first])
                    rect(frame,door_x-1,row,3,63-row,WATER)
                    rect(frame,door_x-1,row,3,1,WHITE)
                    rect(frame,door_x-1,lever_y+4,3,5,WOOD)
                else:
                    rect(frame,door_x-1,lever_y+6,3,42 if tutorial else 25,WOOD)
                    for stripe in range(lever_y+9,63,6):
                        rect(frame,door_x-1,stripe,3,1,DARK)
            rect(frame,lever_x-1,lever_y-3,3,7,DARK)
            line(frame,(lever_x,lever_y),(lever_x+(-2 if opened else 2),lever_y-3),WOOD)
        for index,(first,second) in enumerate(data['valves']):
            x,y=valve_point(level,index)
            first_x,first_offset=center(level,first)
            second_x,second_offset=center(level,second)
            ink=SKY if state.valves>>index&1 else DARK
            if not tutorial and index==3:
                line(frame,(38,57),(x,y),ink)
                line(frame,(x,y),(36,35),ink)
            else:
                line(frame,(first_x,60+first_offset),(first_x,y),ink)
                line(frame,(first_x,y),(second_x,y),ink)
                line(frame,(second_x,y),(second_x,60+second_offset),ink)
            rect(frame,x-2,y-1,5,3,DARK)
            rect(frame,x-1,y-2,3,5,DARK)
            rect(frame,x-1,y-1,3,3,WHITE)
            if state.valves>>index&1:
                line(frame,(x-1,y-1),(x+1,y+1),SKY)
            else:
                rect(frame,x,y-1,1,3,DARK)
        for covered in data['covered']:
            x,offset=center(level,covered)
            rect(frame,x-6,39+offset,12,4,MID)
            rect(frame,x-6,39+offset,12,1,DARK)
            if covered==4:
                # Side ledges expose the bed depth without painting a wall
                # across the navigable mouth of the passing berth.
                rect(frame,x-6,58+offset,2,5,GRAY)
                rect(frame,x+4,58+offset,2,5,GRAY)
                line(frame,(x-4,58+offset),(x+3,60+offset),SKY)
            else:
                rect(frame,x-6,58+offset,12,5,GRAY)
                rect(frame,x-6,58+offset,12,1,DARK)
        for index,goal in enumerate(data['goals']):
            x,_=center(level,goal)
            dock_y=58 if index==1 else 46
            dock_x=0 if index==1 else min(58,x+5)
            rect(frame,dock_x,dock_y,5,2,WOOD)
            rect(frame,dock_x+1,dock_y+2,1,63-dock_y,DARK)
            if index==0:
                rect(frame,dock_x+2,dock_y-8,1,8,DARK)
                rect(frame,dock_x+3,dock_y-8,3,2,GREEN)
            else:
                rect(frame,dock_x,dock_y-3,2,2,WOOD)
                rect(frame,dock_x+3,dock_y-3,2,2,WOOD)
            if state.boats[index]<0:
                rect(frame,dock_x,dock_y-1,5,1,GREEN)
        for command,_ in controls(level,state):
            if command[0]=='sail':
                after=transition(level,state,command)
                if after!=state and not after.failed:
                    target=command[1];x,offset=center(level,target)
                    boat(frame,x,water_row(shown[target])+offset,state.selected,True)
        for index,origin in enumerate(state.boats):
            if origin<0:
                continue
            x,offset=center(level,origin)
            y=water_row(shown[origin])+offset
            if game.animation is not None:
                target=game.animation['after'].boats[index]
                target=data['goals'][index] if target<0 else target
                target_x,target_offset=center(level,target)
                x+=(target_x-x)*amount
                y+=(water_row(shown[target])+target_offset-y)*amount
            boat(frame,x,y,index)
            if len(state.boats)>1 and state.selected==index:
                rect(frame,x-7,y-2,1,3,YELLOW)
                rect(frame,x+7,y-2,1,3,YELLOW)
        self.feedback(frame,shown)
        return frame

    def feedback(self,frame,shown):
        game,state=self.game,self.game.st
        level=game.level_index
        if game.feedback is not None and game.refused and game.animation is None:
            x,y=game.feedback
            radius=2+game.pulse
            for dx,dy in ((-radius,0),(radius,0),(0,-radius),(0,radius)):
                rect(frame,x+dx,y+dy,1,1,RED)
            if game.last_command[0]=='gate':
                for basin_index in LEVELS[level]['gates'][game.last_command[1]]:
                    center_x,offset=center(level,basin_index)
                    rect(frame,center_x-3,water_row(shown[basin_index])+offset,7,1,RED)
        if game.rejected_water is not None:
            state=game.rejected_water
        if state.failed:
            if state.failed in ('roof','bed'):
                basin_index=state.boats[state.selected]
                # Highlight every occupied covered reach responsible for a loss.
                for index,basin_index in enumerate(state.boats):
                    if basin_index in LEVELS[level]['covered']:
                        center_x,offset=center(level,basin_index)
                        low,high=(1,3) if index==0 else (4,6)
                        row=water_row(state.heights[basin_index])
                        if row>water_row(low) or row<water_row(high):
                            rect(frame,center_x-6,(39 if state.failed=='roof' else 58)+offset,12,2,RED)
            else:
                for basin_index in range(1,len(shown)):
                    center_x,offset=center(level,basin_index)
                    rect(frame,center_x-2,water_row(shown[basin_index])+offset,5,1,RED)


class Lq01(ARCBaseGame):
    def __init__(self):
        self.st,self.history=initial(0),[]
        self.animation,self.feedback=None,None
        self.rejected_water=None
        self.refused,self.pulse=False,0
        self.last_command=('invalid',)
        self.display=LockDisplay(self)
        levels=[Level(sprites=[],grid_size=(64,64),name=data['name']) for data in LEVELS]
        super().__init__('lq01',levels,Camera(0,0,64,64,STONE,STONE,[self.display]),False,len(levels),[6,7])

    def on_set_level(self,level):
        self.st,self.history=initial(self.level_index),[]
        self.animation,self.feedback=None,None
        self.rejected_water=None
        self.refused,self.pulse=False,0
        self.last_command=('invalid',)

    def handle_reset(self):
        if self._state in (GameState.NOT_PLAYED,GameState.WIN):
            self.full_reset()
        else:
            self.level_reset()

    def finish(self,after):
        self.st,self.animation=after,None
        if after.failed:
            self.lose()
        elif after.won:
            self.next_level()
        self.complete_action()

    def step(self):
        action=self.action.id.value
        if action==0:
            self.complete_action();return
        if self.animation is not None:
            self.animation['frame']+=1
            if self.animation['frame']>=11:
                self.finish(self.animation['after'])
            return
        before=self.st
        self.rejected_water=None
        self.pulse^=1
        if action==7:
            after=self.history.pop() if self.history else before
            basin_index=before.boats[before.selected]
            x,offset=center(self.level_index,basin_index)
            self.feedback=(x,water_row(before.heights[basin_index])+offset-2)
            self.last_command=('undo',)
        else:
            x,y=self.action.data.get('x'),self.action.data.get('y')
            valid=all(isinstance(value,(int,float)) and isfinite(value) for value in (x,y))
            self.feedback=(max(1,min(62,int(x))),max(1,min(62,int(y)))) if valid else (1,1)
            self.last_command=command_at(self.level_index,before,x,y) if action==6 else ('invalid',)
            after=transition(self.level_index,before,self.last_command)
            if after==before and self.last_command[0] in ('gate','valve'):
                candidate=water_action(self.level_index,before,self.last_command)
                if candidate.failed in ('roof','bed'):
                    self.rejected_water=candidate
            if after!=before:
                self.history.append(before)
        self.refused=after==before
        if after.heights!=before.heights or after.boats!=before.boats:
            self.animation={'after':after,'frame':0};return
        self.finish(after)
