"""a199 Capability Graph -- assemble the smallest enabled dependency network."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,CANVAS,NODE_A,NODE_B,NODE_C,EDGE,CURSOR,REACHABLE,REDUNDANT,GOAL=9,1,12,14,10,8,13,4,6,5
BAD=15
EDGES=((0,1),(0,2),(1,3),(2,3),(2,4),(3,5),(4,5),(5,6),(4,7),(7,6))
LEVELS=[
 {"name":"Enable Module","seq":(1,)},{"name":"Move Cursor","seq":(2,)},
 {"name":"Change Goal","seq":(3,1)},{"name":"Propagate Capability","seq":(1,2,3,4,2)},
 {"name":"Prune Redundancy","seq":(1,3,2,1,4,3,2)},{"name":"Capability Graph","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def audit(enabled,goal):
 seen={0} if enabled&1 else set()
 for _ in range(8):
  for u,v in EDGES:
   if u in seen and (enabled>>v)&1:seen.add(v)
 return int(goal in seen),max(0,enabled.bit_count()-len(seen))
def advance(s,a):
 enabled,cursor,goal,reachable,redundant,history,snapshot=s
 if a==1:enabled^=1<<cursor;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%8;history=(history+(2,))[-8:]
 elif a==3:goal=5+(goal-4)%3;history=(history+(3,))[-8:]
 elif a==4:reachable,redundant=audit(enabled,goal);history=(history+(4,))[-8:]
 elif a==5:snapshot=(enabled,cursor,goal,reachable,redundant,history)
 return enabled,cursor,goal,reachable,redundant,history,snapshot
for q in LEVELS:
 s=(0b11111111,0,6,1,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=CANVAS;pos=((7,27),(20,12),(20,42),(33,18),(33,40),(46,23),(52,36),(44,47))
  for u,v in EDGES:
   x1,y1=pos[u];x2,y2=pos[v];f[min(y1,y2)+3:max(y1,y2)+5,min(x1,x2)+3:min(x1,x2)+5]=EDGE
  for i,(x,y) in enumerate(pos):
   col=GOAL if i==g.goal else NODE_A if i%3==0 else NODE_B if i%3==1 else NODE_C;f[y:y+7,x:x+7]=col if (g.enabled>>i)&1 else BG
   if i==g.cursor:f[y-2:y,x:x+7]=CURSOR
  f[53:57,8:28]=REACHABLE if g.reachable else REDUNDANT;f[53:57,43:43+min(4,g.redundant)*4]=REDUNDANT
  if g.bad:f[1:4,18:46]=BAD
  return f
class A199(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a199",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.enabled,self.cursor,self.goal,self.reachable,self.redundant,self.history,self.snapshot=(0b11111111,0,6,1,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.enabled,self.cursor,self.goal,self.reachable,self.redundant,self.history,self.snapshot=advance((self.enabled,self.cursor,self.goal,self.reachable,self.redundant,self.history,self.snapshot),a)
  elif a==6:
   if (self.enabled,self.cursor,self.goal,self.reachable,self.redundant,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
