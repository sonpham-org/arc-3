"""q617 Spectrum Grammar -- compose grouped color packets through transforming prism relays."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,GALLERY,PRISM,PACKET,GROUP,RELAY,CODE,GOAL,BAD=3,9,12,14,6,10,11,13,15
LEVELS=[
 {"name":"Color Word","seq":(1,2,4)},{"name":"Prism Phrase","seq":(2,3,4,5)},
 {"name":"Nested Packet","seq":(1,3,2,4,4)},{"name":"Relay Transform","seq":(3,1,4,2,5,4)},
 {"name":"Grouped Spectrum","seq":(1,2,4,3,5,2,4)},
 {"name":"Spectrum Grammar","seq":(2,1,3,4,5,2,3,4,1,4)}]
def advance(s,a):
 stack,relay,history,locked=s;stack=list(stack)
 if a in (1,2,3):stack.append((a+relay)%6)
 elif a==4:
  if len(stack)<2:return None
  b=stack.pop();c=stack.pop();stack.append((2*c+b+relay)%6)
 elif a==5:relay=(relay+1)%3;stack=[(v+relay)%6 for v in stack]
 history=history+(a,);return tuple(stack),relay,history,locked
for x in LEVELS:
 s=((),0,(),None)
 for a in x["seq"]:s=advance(s,a);assert s is not None
 t=advance(s,5);x["plan"]=x["seq"]+(5,);x["target"]=t[:3]+((t[0],t[1]),)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GALLERY
  for i in range(4):
   x=8+i*13;f[8:29,x:x+8]=PRISM;f[12+i%2*8:18+i%2*8,x+2:x+6]=RELAY
  for i,v in enumerate(g.stack[-6:]):
   x=8+i*8;f[10:27,x:x+6]=PRISM;f[13+v:19+v,x+2:x+5]=PACKET if v%2 else GROUP
  for i,a in enumerate(g.history[-8:]):f[34:39,8+i*6:13+i*6]=CODE if a==4 else RELAY
  f[46:51,8:8+g.relay*18+10]=RELAY;f[54:58,8:8+(sum(g.stack)%6)*8+5]=PACKET
  if g.locked:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q617(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q617",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.stack=();self.relay=0;self.history=();self.locked=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.stack,self.relay,self.history,self.locked),a)
   if s is None:self.bad=True;self.lose()
   else:
    self.stack,self.relay,self.history,self.locked=s
    if a==5:self.locked=(self.stack,self.relay)
  elif a==6:
   if (self.stack,self.relay,self.history,self.locked)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
