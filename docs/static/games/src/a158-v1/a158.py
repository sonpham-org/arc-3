"""a158 Relational Category -- category membership changes with local group context."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,TABLE,OBJECT_A,OBJECT_B,GROUP_A,GROUP_B,SMALLEST,CURSOR,MATCH,ERROR=10,8,12,14,9,13,4,11,6,7
BAD=15
SIZES=(1,2,3,2,4,1)
LEVELS=[
 {"name":"Move Between Groups","seq":(1,)},{"name":"Select Object","seq":(2,)},
 {"name":"Mark Category","seq":(3,1)},{"name":"Recompute Smallest","seq":(1,2,3,4,2)},
 {"name":"Change Context","seq":(1,3,2,1,4,3,2)},{"name":"Relational Category","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 groups,marked,cursor,matches,errors,history,snapshot=s;gr=list(groups)
 if a==1:gr[cursor]=1-gr[cursor];history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%6;history=(history+(2,))[-8:]
 elif a==3:marked^=1<<cursor;history=(history+(3,))[-8:]
 elif a==4:
  truth=[]
  for i,size in enumerate(SIZES):members=[SIZES[j] for j,g in enumerate(gr) if g==gr[i]];truth.append(size==min(members))
  matches=sum(int(bool((marked>>i)&1)==truth[i]) for i in range(6));errors=6-matches;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(gr),marked,cursor,matches,errors,history)
 return tuple(gr),marked,cursor,matches,errors,history,snapshot
for q in LEVELS:
 s=((0,0,0,1,1,1),0b100001,0,4,2,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=TABLE;f[8:55,31:34]=GROUP_A
  for i,(group,size) in enumerate(zip(g.groups,SIZES)):
   x=(10 if group==0 else 38)+(i%3)*7;y=13+(i//3)*20;w=4+size*2;f[y:y+w,x:x+w]=OBJECT_A if group==0 else OBJECT_B
   if (g.marked>>i)&1:f[y+2:y+5,x+2:x+5]=SMALLEST
   if i==g.cursor:f[y-3:y,x:x+w]=CURSOR
  f[54:58,8:8+g.matches*7]=MATCH;f[7:10,8:8+g.errors*7]=ERROR
  if g.bad:f[1:4,18:46]=BAD
  return f
class A158(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a158",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.groups,self.marked,self.cursor,self.matches,self.errors,self.history,self.snapshot=((0,0,0,1,1,1),0b100001,0,4,2,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.groups,self.marked,self.cursor,self.matches,self.errors,self.history,self.snapshot=advance((self.groups,self.marked,self.cursor,self.matches,self.errors,self.history,self.snapshot),a)
  elif a==6:
   if (self.groups,self.marked,self.cursor,self.matches,self.errors,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
