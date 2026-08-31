"""a177 Constructive Gate -- synthesize a new relational witness."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,WORKBENCH,CELL_A,CELL_B,LINK,ANCHOR,CURSOR,WITNESS,SATISFIED,MISSING=14,8,12,10,9,13,11,4,6,7
BAD=15
LEVELS=[
 {"name":"Toggle Cell","seq":(1,)},{"name":"Select Cell","seq":(2,)},
 {"name":"Add Relation","seq":(3,1)},{"name":"Construct Example","seq":(1,2,3,4,2)},
 {"name":"Satisfy Property","seq":(1,3,2,1,4,3,2)},{"name":"Constructive Gate","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 cells,cursor,links,satisfied,missing,history,snapshot=s
 if a==1:cells^=1<<cursor;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%9;history=(history+(2,))[-8:]
 elif a==3:links^=1<<(cursor%6);history=(history+(3,))[-8:]
 elif a==4:satisfied=sum(int((cells>>i)&1 and (links>>(i%6))&1) for i in range(9));missing=max(0,4-satisfied);history=(history+(4,))[-8:]
 elif a==5:snapshot=(cells,cursor,links,satisfied,missing,history)
 return cells,cursor,links,satisfied,missing,history,snapshot
for q in LEVELS:
 s=(0b000010001,0,0b000101,1,3,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=WORKBENCH
  for i in range(9):
   x=11+(i%3)*16;y=12+(i//3)*15;f[y:y+11,x:x+11]=CELL_A if (g.cells>>i)&1 else CELL_B
   if (g.links>>(i%6))&1:f[y+3:y+8,x+3:x+8]=LINK
   if i==g.cursor:f[y-3:y,x:x+11]=CURSOR
  f[54:58,8:8+g.satisfied*8]=SATISFIED;f[7:10,8:8+g.missing*8]=MISSING;f[54:58,50:57]=WITNESS
  if g.bad:f[1:4,18:46]=BAD
  return f
class A177(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a177",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.cells,self.cursor,self.links,self.satisfied,self.missing,self.history,self.snapshot=(0b000010001,0,0b000101,1,3,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.cells,self.cursor,self.links,self.satisfied,self.missing,self.history,self.snapshot=advance((self.cells,self.cursor,self.links,self.satisfied,self.missing,self.history,self.snapshot),a)
  elif a==6:
   if (self.cells,self.cursor,self.links,self.satisfied,self.missing,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
