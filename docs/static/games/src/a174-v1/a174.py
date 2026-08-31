"""a174 Bisimulation Bridge -- pair two worlds by reciprocal transition matching."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,BRIDGE,WORLD_A,WORLD_B,STATE_A,STATE_B,PAIR,PROBE,CURSOR,RECIPROCAL=11,8,7,13,12,14,9,10,4,6
BAD=15
TRUE_PAIR=(2,0,1,5,3,4)
LEVELS=[
 {"name":"Change Pair","seq":(1,)},{"name":"Select State","seq":(2,)},
 {"name":"Probe Transition","seq":(3,1)},{"name":"Match Both Directions","seq":(1,2,3,4,2)},
 {"name":"Transfer Route","seq":(1,3,2,1,4,3,2)},{"name":"Bisimulation Bridge","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 pairs,cursor,probe,reciprocal,errors,history,snapshot=s;p=list(pairs)
 if a==1:p[cursor]=(p[cursor]+1)%6;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%6;history=(history+(2,))[-8:]
 elif a==3:probe=(probe+1)%4;history=(history+(3,))[-8:]
 elif a==4:reciprocal=sum(int(p[i]==TRUE_PAIR[i] and p[TRUE_PAIR[i]]==TRUE_PAIR[TRUE_PAIR[i]]) for i in range(6));errors=6-reciprocal;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(p),cursor,probe,reciprocal,errors,history)
 return tuple(p),cursor,probe,reciprocal,errors,history,snapshot
for q in LEVELS:
 s=((2,0,1,5,3,4),0,0,6,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:30]=WORLD_A;f[4:60,34:60]=WORLD_B
  for i,p in enumerate(g.pairs):
   y=9+i*8;f[y:y+6,8:16]=STATE_A;f[9+p*8:15+p*8,48:56]=STATE_B;f[min(y+2,11+p*8):max(y+3,12+p*8),16:48]=PAIR
   if i==g.cursor:f[y-3:y,7:17]=CURSOR
  f[54:58,8:8+g.reciprocal*7]=RECIPROCAL;f[7:10,8:8+g.probe*9]=PROBE;f[54:58,51:51+g.errors]=BAD
  if g.bad:f[1:4,18:46]=BAD
  return f
class A174(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a174",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.pairs,self.cursor,self.probe,self.reciprocal,self.errors,self.history,self.snapshot=((2,0,1,5,3,4),0,0,6,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.pairs,self.cursor,self.probe,self.reciprocal,self.errors,self.history,self.snapshot=advance((self.pairs,self.cursor,self.probe,self.reciprocal,self.errors,self.history,self.snapshot),a)
  elif a==6:
   if (self.pairs,self.cursor,self.probe,self.reciprocal,self.errors,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
