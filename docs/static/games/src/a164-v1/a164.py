"""a164 Bidirectional Hunt -- grow reversible frontiers from both ends until they meet."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,MAZE,START_FRONT,TARGET_FRONT,UNKNOWN,MEET,EXPAND,CURSOR,BUDGET,OVERLAP=0,8,12,14,7,4,10,13,11,6
BAD=15
LEVELS=[
 {"name":"Expand Frontier","seq":(1,)},{"name":"Switch Side","seq":(2,)},
 {"name":"Select Node","seq":(3,1)},{"name":"Meet in Middle","seq":(1,2,3,4,2)},
 {"name":"Balance Frontiers","seq":(1,3,2,1,4,3,2)},{"name":"Bidirectional Hunt","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 start_front,target_front,side,cursor,budget,meet,overlap,history,snapshot=s
 if a==1:
  if side==0:start_front|=1<<cursor
  else:target_front|=1<<cursor
  budget=(budget+1)%12;history=(history+(1,))[-8:]
 elif a==2:side=1-side;history=(history+(2,))[-8:]
 elif a==3:cursor=(cursor+1)%12;history=(history+(3,))[-8:]
 elif a==4:overlap=(start_front&target_front).bit_count();meet=int(overlap>0);history=(history+(4,))[-8:]
 elif a==5:snapshot=(start_front,target_front,side,cursor,budget,meet,overlap,history)
 return start_front,target_front,side,cursor,budget,meet,overlap,history,snapshot
for q in LEVELS:
 s=(1,1<<11,0,0,0,0,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=MAZE
  for i in range(12):
   x=8+(i%4)*13;y=11+(i//4)*15;col=MEET if ((g.start_front>>i)&1 and (g.target_front>>i)&1) else START_FRONT if (g.start_front>>i)&1 else TARGET_FRONT if (g.target_front>>i)&1 else UNKNOWN;f[y:y+11,x:x+11]=col
   if i==g.cursor:f[y-3:y,x:x+11]=CURSOR
  f[54:58,8:8+g.budget*4]=BUDGET;f[7:10,8:8+g.overlap*10]=OVERLAP
  if g.bad:f[1:4,18:46]=BAD
  return f
class A164(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a164",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.start_front,self.target_front,self.side,self.cursor,self.budget,self.meet,self.overlap,self.history,self.snapshot=(1,1<<11,0,0,0,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.start_front,self.target_front,self.side,self.cursor,self.budget,self.meet,self.overlap,self.history,self.snapshot=advance((self.start_front,self.target_front,self.side,self.cursor,self.budget,self.meet,self.overlap,self.history,self.snapshot),a)
  elif a==6:
   if (self.start_front,self.target_front,self.side,self.cursor,self.budget,self.meet,self.overlap,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
