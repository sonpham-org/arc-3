"""a106 Shadow Packing -- satisfy front and side silhouettes at once."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,STUDIO,BIN,SOLID_A,SOLID_B,FRONT,SIDE,GAP,EXCESS,BAD=2,8,9,12,14,10,13,4,11,15
LEVELS=[
 {"name":"Move Depth","seq":(1,)},{"name":"Select Solid","seq":(3,)},
 {"name":"Move Across","seq":(2,1)},{"name":"Compare Shadows","seq":(1,3,2,4,1)},
 {"name":"Fill Both Views","seq":(2,1,3,2,1,4,3)},{"name":"Shadow Packing","seq":(1,2,3,1,4,2,3,1,4,2)},
]
def advance(s,a):
 positions,cursor,front,side,gaps,excess,history,snapshot=s;p=[list(x) for x in positions]
 if a==1:p[cursor][1]=(p[cursor][1]+1)%4;history=(history+(1,))[-8:]
 elif a==2:p[cursor][0]=(p[cursor][0]+1)%4;history=(history+(2,))[-8:]
 elif a==3:cursor=(cursor+1)%4;history=(history+(3,))[-8:]
 elif a==4:
  front=tuple(sorted({x for x,z in p}));side=tuple(sorted({z for x,z in p}));gaps=(4-len(front))+(4-len(side));excess=sum(int([x for x in p].count(q)>1) for q in p)%6;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(map(tuple,p)),cursor,front,side,gaps,excess,history)
 return tuple(map(tuple,p)),cursor,front,side,gaps,excess,history,snapshot
for x in LEVELS:
 s=(((0,0),(1,1),(2,0),(3,2)),0,(),(),8,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=STUDIO;f[15:47,16:48]=BIN
  for i,(x,z) in enumerate(g.positions):px=18+x*7+z*2;py=39-z*7;f[py:py+8,px:px+8]=SOLID_A if i%2==0 else SOLID_B
  f[9:13,10:28]=FRONT;f[50:55,10:28]=SIDE
  for i,v in enumerate(g.front):f[8:14,31+v*6:36+v*6]=FRONT
  for i,v in enumerate(g.side):f[50:56,31+v*6:36+v*6]=SIDE
  f[7:10,8:8+g.gaps*5]=GAP;f[56:59,8:8+g.excess*5]=EXCESS
  if g.bad:f[1:4,18:46]=BAD
  return f
class A106(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a106",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.positions,self.cursor,self.front,self.side,self.gaps,self.excess,self.history,self.snapshot=(((0,0),(1,1),(2,0),(3,2)),0,(),(),8,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.positions,self.cursor,self.front,self.side,self.gaps,self.excess,self.history,self.snapshot=advance((self.positions,self.cursor,self.front,self.side,self.gaps,self.excess,self.history,self.snapshot),a)
  elif a==6:
   if (self.positions,self.cursor,self.front,self.side,self.gaps,self.excess,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
