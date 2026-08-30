"""q587 Spectrum Counter -- shape an adaptive opponent and transfer the learned relation across representations."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GALLERY,PRISM,LIGHT,OPPONENT,TRANSFER,CLAIM,BAD=2,4,15,14,12,11,13,8
LEVELS=[
 {"name":"First Counter","plan":(1,2,4),"claim":0},{"name":"Repeated Light","plan":(2,2,4,1),"claim":1},
 {"name":"Shaped Tactic","plan":(3,1,3,4,2),"claim":2},{"name":"Relational Transfer","plan":(1,2,1,4,3,2),"claim":1},
 {"name":"Counter Cycle","plan":(2,3,2,4,1,3,1),"claim":2},{"name":"Spectrum Counter","plan":(3,1,2,3,4,2,1,3),"claim":0}]
def advance(s,a):
 recent,opponent,representation,value=s
 if a==4:representation^=1;value=(2*value+opponent+1)%7
 else:
  opponent=(a%3) if not recent or recent[-1]!=a else a%3+1;opponent%=3;recent=(recent+(a,))[-2:];value=(value+a+opponent+representation)%7
 return recent,opponent,representation,value
def target(x):
 s=((),0,0,0)
 for a in x["plan"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=GALLERY
  for i in range(3):f[11:25,9+i*17:20+i*17]=LIGHT if i==g.opponent else PRISM
  f[31:38,8:8+g.value*7]=TRANSFER;f[43:48,8:29 if g.representation else 16]=TRANSFER;f[51:55,8:8+g.opponent*14]=OPPONENT;f[56:60,8:8+g.claim*14]=CLAIM
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q587(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.recent=();self.opponent=self.representation=self.value=self.claim=0;self.target=target(LEVELS[0]);self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q587",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.recent=();self.opponent=self.representation=self.value=self.claim=0;self.target=target(LEVELS[self.level_index]);self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4):self.recent,self.opponent,self.representation,self.value=advance((self.recent,self.opponent,self.representation,self.value),a)
  elif a==5:self.claim=(self.claim+1)%3
  elif a==6:
   if (self.recent,self.opponent,self.representation,self.value)==self.target and self.claim==x["claim"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
