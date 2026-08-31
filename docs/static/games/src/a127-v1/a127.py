"""a127 Triad Ban -- satisfy overlapping three-cell hypergraph constraints."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,BOARD,STATE_A,STATE_B,SEED,TRIAD,SELECT,VALID,VIOLATION,BAD=9,8,12,14,10,11,13,4,6,15
TRIADS=((0,1,4),(1,2,4),(3,4,6),(4,5,8),(4,6,8),(0,4,8))
LEVELS=[
 {"name":"Fill Cell","seq":(1,)},{"name":"Select Cell","seq":(2,)},
 {"name":"Inspect Triad","seq":(3,1)},{"name":"Break Monochrome","seq":(1,2,3,4,2)},
 {"name":"Overlap Constraints","seq":(1,3,2,1,4,3,2)},{"name":"Triad Ban","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 states,cursor,overlay,violations,valid,history,snapshot=s;st=list(states)
 if a==1:st[cursor]=1-st[cursor];history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%9;history=(history+(2,))[-8:]
 elif a==3:overlay=(overlay+1)%len(TRIADS);history=(history+(3,))[-8:]
 elif a==4:violations=sum(int(st[x]==st[y]==st[z]) for x,y,z in TRIADS);valid=len(TRIADS)-violations;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(st),cursor,overlay,violations,valid,history)
 return tuple(st),cursor,overlay,violations,valid,history,snapshot
for q in LEVELS:
 s=((0,1,0,1,0,1,0,1,0),0,0,0,6,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=BOARD;pts=[]
  for i,state in enumerate(g.states):
   x=11+(i%3)*18;y=11+(i//3)*15;pts.append((x+6,y+6));f[y:y+12,x:x+12]=STATE_A if state==0 else STATE_B
   if i in (0,8):f[y+3:y+9,x+3:x+9]=SEED
   if i==g.cursor:f[y-3:y,x:x+12]=SELECT
  for i in TRIADS[g.overlay]:
   x,y=pts[i];f[y-2:y+3,x-2:x+3]=TRIAD
  f[54:58,8:8+g.valid*7]=VALID;f[7:10,8:8+g.violations*8]=VIOLATION
  if g.bad:f[1:4,18:46]=BAD
  return f
class A127(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a127",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.states,self.cursor,self.overlay,self.violations,self.valid,self.history,self.snapshot=((0,1,0,1,0,1,0,1,0),0,0,0,6,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.states,self.cursor,self.overlay,self.violations,self.valid,self.history,self.snapshot=advance((self.states,self.cursor,self.overlay,self.violations,self.valid,self.history,self.snapshot),a)
  elif a==6:
   if (self.states,self.cursor,self.overlay,self.violations,self.valid,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
