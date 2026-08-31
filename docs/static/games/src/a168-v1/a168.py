"""a168 Dynamic Frontier -- maintain reachable unknowns as corridors open and close."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,MAP,REGION,OPEN,CLOSED,FRONTIER,INSPECTED,CURSOR,REACHABLE,ORPHAN=4,8,7,10,6,14,12,13,4,11
BAD=15
LEVELS=[
 {"name":"Inspect Region","seq":(1,)},{"name":"Select Region","seq":(2,)},
 {"name":"Apply Local Rule","seq":(3,1)},{"name":"Update Frontier","seq":(1,2,3,4,2)},
 {"name":"Avoid Orphan","seq":(1,3,2,1,4,3,2)},{"name":"Dynamic Frontier","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 open_mask,frontier,inspected,cursor,rule,reachable,orphaned,history,snapshot=s
 if a==1:
  inspected|=1<<cursor;open_mask^=(1<<((cursor+1)%12))|(1<<((cursor-1)%12));frontier=(open_mask&~inspected);history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%12;history=(history+(2,))[-8:]
 elif a==3:rule=(rule+1)%3;cursor=(cursor+rule+1)%12;history=(history+(3,))[-8:]
 elif a==4:reachable=frontier.bit_count();orphaned=(~open_mask&~inspected&((1<<12)-1)).bit_count();history=(history+(4,))[-8:]
 elif a==5:snapshot=(open_mask,frontier,inspected,cursor,rule,reachable,orphaned,history)
 return open_mask,frontier,inspected,cursor,rule,reachable,orphaned,history,snapshot
for q in LEVELS:
 s=(0b101010101010,0b101010101010,0,0,0,6,6,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=MAP
  for i in range(12):
   x=8+(i%4)*13;y=11+(i//4)*15;col=INSPECTED if (g.inspected>>i)&1 else FRONTIER if (g.frontier>>i)&1 else OPEN if (g.open_mask>>i)&1 else CLOSED;f[y:y+11,x:x+11]=col
   if i==g.cursor:f[y-3:y,x:x+11]=CURSOR
  f[54:58,8:8+g.reachable*6]=REACHABLE;f[7:10,8:8+g.orphaned*6]=ORPHAN
  if g.bad:f[1:4,18:46]=BAD
  return f
class A168(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a168",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.open_mask,self.frontier,self.inspected,self.cursor,self.rule,self.reachable,self.orphaned,self.history,self.snapshot=(0b101010101010,0b101010101010,0,0,0,6,6,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.open_mask,self.frontier,self.inspected,self.cursor,self.rule,self.reachable,self.orphaned,self.history,self.snapshot=advance((self.open_mask,self.frontier,self.inspected,self.cursor,self.rule,self.reachable,self.orphaned,self.history,self.snapshot),a)
  elif a==6:
   if (self.open_mask,self.frontier,self.inspected,self.cursor,self.rule,self.reachable,self.orphaned,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
