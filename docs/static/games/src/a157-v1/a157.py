"""a157 Disjunctive Class -- select two distant clusters linked by a relation."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,FIELD,CLUSTER_A,CLUSTER_B,MIDDLE,RELATION,SELECTED,CURSOR,CORRECT,ERROR=9,8,12,14,7,10,13,11,4,6
BAD=15
POINTS=((0,0),(1,0),(0,1),(4,4),(5,4),(4,5),(2,2),(3,2))
LEVELS=[
 {"name":"Select Member","seq":(1,)},{"name":"Move Cursor","seq":(2,)},
 {"name":"Change Relation","seq":(3,1)},{"name":"Find Two Clusters","seq":(1,2,3,4,2)},
 {"name":"Reject Middle","seq":(1,3,2,1,4,3,2)},{"name":"Disjunctive Class","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 selected,cursor,relation,correct,errors,history,snapshot=s
 if a==1:selected^=1<<cursor;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%8;history=(history+(2,))[-8:]
 elif a==3:relation=(relation+1)%3;history=(history+(3,))[-8:]
 elif a==4:truth=[i<6 and ((x+y+relation)%2==relation%2) for i,(x,y) in enumerate(POINTS)];correct=sum(int(bool((selected>>i)&1)==truth[i]) for i in range(8));errors=8-correct;history=(history+(4,))[-8:]
 elif a==5:snapshot=(selected,cursor,relation,correct,errors,history)
 return selected,cursor,relation,correct,errors,history,snapshot
for q in LEVELS:
 s=(0b00110011,0,0,5,3,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FIELD
  for i,(x,y) in enumerate(POINTS):
   px=9+x*8;py=9+y*8;col=CLUSTER_A if i<3 else CLUSTER_B if i<6 else MIDDLE;f[py:py+7,px:px+7]=col
   if (g.selected>>i)&1:f[py+2:py+5,px+2:px+5]=SELECTED
   if i==g.cursor:f[py-3:py,px:px+7]=CURSOR
  f[54:58,8:8+g.correct*6]=CORRECT;f[7:10,8:8+g.errors*6]=ERROR;f[54:58,51:58]=RELATION
  if g.bad:f[1:4,18:46]=BAD
  return f
class A157(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a157",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.selected,self.cursor,self.relation,self.correct,self.errors,self.history,self.snapshot=(0b00110011,0,0,5,3,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.selected,self.cursor,self.relation,self.correct,self.errors,self.history,self.snapshot=advance((self.selected,self.cursor,self.relation,self.correct,self.errors,self.history,self.snapshot),a)
  elif a==6:
   if (self.selected,self.cursor,self.relation,self.correct,self.errors,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
