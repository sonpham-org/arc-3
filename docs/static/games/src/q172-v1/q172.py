"""q172 Fluid Blend -- route two conserved fluid components to exact visual mixtures."""

from __future__ import annotations
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,LAB,GLASS,A,B,MIX,TARGET,CURSOR,BAD=15,0,1,9,6,10,14,11,8
LEVELS=[
 {"name":"One Pour","start":[(2,0),(0,0)],"target":[(1,0),(1,0)],"ops":[(0,1,0)],"budget":4},
 {"name":"Two Colors","start":[(2,0),(0,2)],"target":[(1,1),(1,1)],"ops":[(0,1,0),(1,0,1)],"budget":6},
 {"name":"Three Glasses","start":[(3,0),(0,3),(0,0)],"target":[(2,1),(1,1),(0,1)],"ops":[(0,1,0),(1,2,1),(1,0,1)],"budget":9},
 {"name":"Blend Ratios","start":[(4,0),(0,4),(0,0)],"target":[(2,1),(1,2),(1,1)],"ops":[(0,2,0),(1,2,1),(0,1,0),(1,0,1)],"budget":12},
 {"name":"Conserved Hue","start":[(4,0),(0,4),(0,0),(0,0)],"target":[(2,1),(1,2),(1,1),(0,0)],"ops":[(0,2,0),(1,2,1),(0,1,0),(1,0,1),(2,3,0)],"budget":14},
 {"name":"Fluid Blend","start":[(5,0),(0,5),(0,0),(0,0)],"target":[(2,1),(1,2),(1,1),(1,1)],"ops":[(0,2,0),(1,2,1),(0,3,0),(1,3,1),(0,1,0),(1,0,1)],"budget":18},
]


def pour(values,op):
 src,dst,component=op;out=[list(v) for v in values]
 if out[src][component]>0:out[src][component]-=1;out[dst][component]+=1
 return tuple(tuple(v) for v in out)


class Display(RenderableUserDisplay):
 def __init__(self,game):self.game=game
 def render_interface(self,frame:np.ndarray)->np.ndarray:
  g=self.game;frame[:,:]=BG;frame[8:55,4:60]=LAB;n=len(g.values);gap=48//n
  for i,((a,b),(ta,tb)) in enumerate(zip(g.values,g.target)):
   x=9+i*gap;frame[15:44,x:x+9]=GLASS;frame[18:41,x+2:x+7]=LAB
   frame[41-a*4:41,x+2:x+4]=A;frame[41-b*4:41,x+5:x+7]=B
   frame[12:15,x:x+4]=TARGET if a==ta else A;frame[12:15,x+5:x+9]=TARGET if b==tb else B
  for i in range(len(g.ops)):frame[48:53,6+i*9:13+i*9]=CURSOR if i==g.cursor else MIX
  if g.failed:frame[58:63,25:39]=BAD
  return frame


class Q172(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.values=self.target=();self.ops=[];self.cursor=self.budget_left=0;self.failed=False
  levels=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS]
  super().__init__("q172",levels,Camera(0,0,64,64,BG,BG,[self.display]),False,len(levels),[3,4,5,6])
 def on_set_level(self,level):
  s=LEVELS[self.level_index];self.values=tuple(map(tuple,s["start"]));self.target=tuple(map(tuple,s["target"]));self.ops=list(map(tuple,s["ops"]));self.cursor=0;self.budget_left=s["budget"];self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  self.budget_left-=1
  if a==3:self.cursor=(self.cursor-1)%len(self.ops)
  elif a==4:self.cursor=(self.cursor+1)%len(self.ops)
  elif a==5:self.values=pour(self.values,self.ops[self.cursor])
  elif a==6:
   if self.values==self.target:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  if self.budget_left<=0:self.failed=True;self.lose()
  self.complete_action()
