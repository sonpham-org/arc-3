"""q603 Murmuration Grammar -- compose flock messages while a parity relation detects one decoy."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,AVIARY,FLOCK,WIND,GROUP,PARITY,DECOY,GOAL,BAD=3,10,14,9,6,12,11,13,15
LEVELS=[
 {"name":"Wing Word","seq":(1,2,4)},{"name":"Wind Phrase","seq":(2,3,4,5)},
 {"name":"Decoy Glyph","seq":(1,3,2,4,4)},{"name":"Parity Relay","seq":(3,1,4,2,5,4)},
 {"name":"Grouped Flock","seq":(1,2,4,3,5,2,4)},
 {"name":"Murmuration Grammar","seq":(2,1,3,4,5,2,3,4,1,4)}]
def advance(s,a):
 stack,wind,parity,history,locked=s;v=list(stack)
 if a in (1,2,3):v.append((a+wind)%5);parity^=(a%2)
 elif a==4:
  if len(v)<2:return None
  b=v.pop();c=v.pop();v.append((c+2*b+wind)%5);parity^=((b+c)%2)
 elif a==5:wind=(wind+1)%4;parity^=1
 history=history+(a,)
 if a==5:locked=(tuple(v),wind,parity)
 return tuple(v),wind,parity,history,locked
for x in LEVELS:
 s=((),0,0,(),None)
 for a in x["seq"]:s=advance(s,a);assert s is not None
 t=advance(s,5);x["plan"]=x["seq"]+(5,);x["target"]=t
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=AVIARY
  for i in range(7):x=8+i*7;f[8+(i%2)*7:13+(i%2)*7,x:x+5]=WIND;f[22:25,x:x+3]=FLOCK
  for i,v in enumerate(g.stack[-6:]):x=8+i*8;f[31:38,x:x+6]=GROUP if v%2 else FLOCK;f[39:42,x:x+2+v]=WIND
  for i,a in enumerate(g.history[-7:]):f[46:50,8+i*7:13+i*7]=DECOY if a==5 else PARITY
  f[54:58,8:8+g.parity*25+12]=PARITY
  if g.locked:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q603(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q603",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.stack=();self.wind=self.parity=0;self.history=();self.locked=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.stack,self.wind,self.parity,self.history,self.locked),a)
   if s is None:self.bad=True;self.lose()
   else:self.stack,self.wind,self.parity,self.history,self.locked=s
  elif a==6:
   if (self.stack,self.wind,self.parity,self.history,self.locked)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
